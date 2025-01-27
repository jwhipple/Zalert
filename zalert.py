#!/usr/bin/python3
# /usr/bin/env python3
# Written by Joe Whipple <zalert@whipsys.com> 2024
import os
import re
import sys
import json
import subprocess
import traceback
from apilib import ConnectWiseApi
from apilib import JWZabbix
from collections.abc import Sequence


# Are we using test or prod Connectwise?
# configEnv = 'TestEnv'
configEnv = 'ProdEnv'

# Test event ID to use (valid only if TestEnv is set).
zabbixTestEventId = '82176448'

# Classes
class Config(dict):

    # This is the class to load the config file for the API URL and key's
    def __init__(self, *args, name='zapiconfig.json', **kwargs):
        self.config = os.path.join(os.path.dirname(os.path.realpath(__file__)), name)
        super(Config, self).__init__(*args, **kwargs)

    def load(self):
        """load a JSON config file from disk"""
        try:
            with open(self.config, 'r') as cfgfile:
                self.update(json.load(cfgfile))
        except Exception as e:
            print(f'Error: {e}')
            exit(0)

    def save(self):
        with open(self.config, 'w') as cfgfile:
            cfgfile.write(json.dumps(self))

    def getValue(self, category, setting):
        settingdict = self
        if category:
            if category in self:
                settingdict = self[category]
            else:
                return None

        return settingdict[setting] if setting in settingdict else None


def toCWDateTime(pythonDateTime):
    # Needed to convert dates to CW friendly ones.
    return pythonDateTime.strftime('%Y-%m-%dT%H:%M:%SZ')


def getCompanyForTicket(zabbixEventRecord, companyTagName):
    # Procedure to get company short name. This involves several API's so its placed here.
    # Determine company name to put in ticket:
    # Try to get company name from the host tags first.

    # cwapi.writeDebugLog(f'Trying to find company from tag name {companyTagName}...')
    for tag in zabbixEventRecord[0]['tags']:
        if str.lower(tag['tag']) == companyTagName:
            cwapi.writeDebugLog(f'Got company from tag value: {tag["tag"]} - {zabbixCWCompany}')
            return tag['value']

    # If no tag, try using the host group
    if not zabbixCWCompany:
        # cwapi.writeDebugLog(f'Trying to find company from hostgroups with companyNameFromHostGroups ... in host group name')
        hostgroups = jwzabbixapi.getGroupsForHost(zabbixEventRecord[0]['hosts'][0]['hostid'])['result'][0]['groups']

        # Loop through all the hostgroups for a company. Find any that start with M/ or A/
        # and use that as company shortname.
        for group in hostgroups:
            if group['name'].startswith('A/') or group['name'].startswith('M/'):
                groupmatch = group['name'].split('/')
                if len(groupmatch) > 1:
                    cwapi.writeDebugLog(f'Got company from hostgroup: {group["name"]}')
                    return str.lower(groupmatch[1])

    if not zabbixCWCompany:
        # Company still not found, use hard coded one.
        # cwapi.writeDebugLog(f'No company found from tag or hostgroup, using default: {defaultCompany}')
        return defaultCompany

    cwapi.writeDebugLog(f'Fell through company lookup!')
    return None


def getTagValue(zabbixEventRecord, tagName):
    # Returns the value of an alert tag.
    foundTagValue = ""
    for tag in zabbixEventRecord[0]['tags']:
        if tagName.lower() in tag['tag'].lower():
            # cwapi.writeDebugLog(f"Found tag with a value of {TagName}: {tag['value']}")
            foundTagValue = str(tag['value'])

    return foundTagValue

# Function to check for the specific string in the message
def check_for_ticket_created(ticketSubjectTemplate,eventData):

    # Replace all {variable} placeholders in the template with the regex \d+
    pattern = re.sub(r'\{[^}]+\}', r'\\d+', re.escape(ticketSubjectTemplate))

    # Unescape the regex backslashes for \d+
    pattern = pattern.replace(r'\\d+', r'\d+')

    for event in eventData:
        for ack in event.get('acknowledges', []):
            if re.search(pattern, ack.get('message', '')):
                cwapi.writeDebugLog(f"Found match in Zabbix ack message: {ack.get('message', '')}")
                return True
    return False


def zabbixErrorTicket(errorMsg, area, errorEventID, errorText = ""):
    # Create a ticket if an error is thrown while the script runs.
    zabbixErrorEventRecord = jwzabbixapi.getEventByEventId(errorEventID)
    zabbixErrorTriggerId = zabbixErrorEventRecord[0]['objectid']
    errorCWCompanyName = config.getValue("Global", 'zTicketErrorCompany')
    errorCWCompanyID = cwapi.getCompanyIDbyIdentifier(errorCWCompanyName)
    errorCWBoardName = config.getValue("Global", 'zTicketErrorCWBoard')
    errorCWBoardID = cwapi.getServiceTicketBoardIdFromName(errorCWBoardName).json()[0]['id']
    zabbixCWNewTicketStatusId = cwapi.getServiceTicketBoardStatusDefaultStatus(errorCWBoardID, "Needs Assigned")
    if errorMsg != "":
        zabbixTraceback = traceback.extract_tb(errorMsg.__traceback__)
    else:
        zabbixTraceback = "API error"

    errorTicketInfo = f'Error creating ticket:\r\nArea: {area}\r\nScript Error: {errorMsg}\r\nTraceback: {zabbixTraceback}\r\nZabbix Link: https://monitor.adaptivecloud.com/tr_events.php?triggerid={zabbixErrorTriggerId}&eventid={errorEventID}\r\nReturned Text:\r\n{errorText}'

    ticketErrorTemplate = {
        "summary": "Zabbix zalert.py threw an error when generating a ticket!",
        "recordType": "ServiceTicket",
        "severity": "Medium",
        "impact": "Medium",
        "initialDescription": f"{errorTicketInfo}",

        "board": {
            "id": errorCWBoardID,
        },
        "status": {
            "id": zabbixCWNewTicketStatusId,
        },
        "company": {
            "id": errorCWCompanyID
        }
    }
    if configEnv == 'ProdEnv':
        ticketPost = cwapi.postServiceTicket(ticketErrorTemplate).json()
        ticketID = ticketPost['id']
        jwzabbixapi.writeDebugLog(f'**** Error generating CW ticket in zabbix. CW Ticket: {ticketID} created for this error')
        send_SMS(errorTicketInfo)
    else:
        jwzabbixapi.writeDebugLog(f'Testenv, no error ticket.')
    exit(0)

def send_SMS(message):
    smsAlertNumbers = config.getValue("Global", 'scriptErrorAlertSMS')
    if not smsAlertNumbers:
        cwapi.writeDebugLog("No SMS alert numbers specified. Not sending any SMS text.")
        return

    for smsAlertNumber in smsAlertNumbers:
        smsAlertNumber = str(smsAlertNumber)
        try:
            subprocess.run(['/usr/bin/python3', '/usr/lib/zabbix/alertscripts/zabbixsms.py', smsAlertNumber, message], check=True)
            cwapi.writeDebugLog(f"SMS sent to {smsAlertNumber}")
        except subprocess.CalledProcessError as e:
            cwapi.writeDebugLog(f"Failed to send SMS to {smsAlertNumber}. Error: {e}")
        except FileNotFoundError:
            cwapi.writeDebugLog(f"zabbixsms.py not found or not executable.")

# Return true if the variable has indices, some things like AlertMsgs can have them... or not.
def has_indices(variable):
    return isinstance(variable, Sequence)


# Initialize initial vars.
zabbixEventId = ""
zabbixCWBoard = ""
zabbixCWBoardId = ""

# Load the API config json file
config = Config(name='zapiconfig.json')
config.load()

# Assign variables to config entries for Connectwise API:
cwbaseurl = config.getValue(configEnv, 'cwBaseurl')
cwCompany = config.getValue(configEnv, 'cwCompany')
clientid = config.getValue(configEnv, 'cwClientid')
cwKey = config.getValue(configEnv, 'cwKey')
cwSecret = config.getValue(configEnv, 'cwSecret')
zDebug = config.getValue(configEnv, 'zDebug')

zabbixTicketGenAckMsg = config.getValue(configEnv, 'zabbixTicketGenAckMsg')
zabbixTicketCloseAckMsg = config.getValue(configEnv, 'zabbixTicketCloseAckMsg')


# Grab Global variables from config file:
zURL = config.getValue("Global", 'zURL')
zAPIKey = config.getValue("Global", 'zAPIKey')
defaultCompany = config.getValue("Global", 'companyDefaultValue')   # Default company for tickets
defaultCWBoard = config.getValue("Global", 'defaultCWBoard')   # Default ticket board for CW tickets.
companyTagName = str.lower(config.getValue("Global", 'companyTagName'))   # Tag that specifies company name
companyNameFromHostGroups = config.getValue("Global", 'companyNameFromHostGroups')
cwBoardTagName = str.lower(config.getValue("Global", 'cwBoardTagName'))   # Tag that specifies ticket board to assign tickets to for event.
cwDisableTickets = str.lower(config.getValue("Global", 'cwDisableTickets'))


# Initialize the API's
jwzabbixapi = JWZabbix(zURL, zAPIKey, zDebug)
cwapi = ConnectWiseApi(cwbaseurl, clientid, cwCompany, cwKey, cwSecret, zDebug)

# Start of new instance log.
cwapi.writeDebugLog(f'\r\n\r\n**************************************************')
cwapi.writeDebugLog(f'Script execute started, zabbixEventId: {zabbixEventId}')


# Pull in the arguments for the script. Check to see if we are missing any and if so put test values in.
if len(sys.argv) > 1:
    zabbixEventId = sys.argv[1]
else:
    # Only use the test event ID if we are in Test mode.
    if configEnv == 'TestEnv':
        zabbixEventId = zabbixTestEventId
        cwapi.writeDebugLog(f'*** TestEnv enabled, using Event ID: {zabbixEventId} ***')
    else:
        # zabbixEventId = zabbixTestEventId  # Only if I super-duper wanna use a test event id in prod (also comment out the exit below)
        exit(0)

# Gather the details for the alert based off the Event ID. We search specifically for sendto==Connectwise items.
try:
    zabbixAlertRecord = jwzabbixapi.getAlertByEvent(zabbixEventId)
    # print(f"zabbixAlertRecord:\r\n{zabbixAlertRecord}")
except Exception as e:
    cwapi.writeDebugLog(f'Exception Error  Failure to get Alert Record. {e}')
    zabbixErrorTicket(e, "Retrieving zabbixAlertRecord", zabbixEventId, zabbixAlertRecord.text)
    exit(0)

for event in zabbixAlertRecord:
    if event['eventid'] == zabbixEventId and event['sendto'] == 'Connectwise':
        zabbixAlertRecord = event
        # print(f"event:\r\n{zabbixAlertRecord}")

zabbixEventRecord = jwzabbixapi.getEventByEventId(zabbixEventId)
zabbixTriggerId = zabbixEventRecord[0]['objectid']
zabbixHostName = zabbixEventRecord[0]['hosts'][0]['host']
zabbixHostMacros = json.dumps(jwzabbixapi.getHostMacros(zabbixEventRecord[0]['hosts'][0]['hostid']))
zabbixHostGroups = jwzabbixapi.getGroupsForHost(zabbixEventRecord[0]['hosts'][0]['hostid'])
zabbixCWCompany = ""
zabbixCWBoard = ""
zabbixEventTags = zabbixEventRecord[0]['tags']
zabbixTicketAdditionalMsg = ""  # This is a message to add to the ticket because there is an issue with something like the CSN or other field Zalert had problems with.


# Check to see if disable ticket tag is present for the host:
ticketDisabled = any(item['value'] == '1' for item in zabbixEventTags if str.lower(item['tag']) == cwDisableTickets)
if ticketDisabled:
    cwapi.writeDebugLog(f'Ticket gen tag {cwDisableTickets} is set to disabled.')
    jwzabbixapi.addMessageToProblem(zabbixEventId, 4, f"Ticket generation is disabled for this host or trigger! {cwDisableTickets} is set.")
    cwapi.writeDebugLog(f'No IPP.NoTickets tag found, ticketing is enabled for this host!.')
    sys.exit(1)


# Ticket board search area
# Check for tag overridden boards.
zabbixCWBoard = getTagValue(zabbixEventRecord, cwBoardTagName)
if len(zabbixCWBoard) > 0:
    cwapi.writeDebugLog(f"Using tag for defaultCWBoard for ticket.")
else:
    # Use default ticket board.
    zabbixCWBoard = defaultCWBoard
    cwapi.writeDebugLog(f"Using defaultCWBoard for ticket.")

zabbixCWBoardId = cwapi.getServiceTicketBoardIdFromName(zabbixCWBoard).json()[0]["id"]

# Ticket company search area
# Get company to assign in ticket by looking at tags->hostgroup->default value
zabbixCWCompany = getCompanyForTicket(zabbixEventRecord, companyTagName)

# Company ID lookup from name:
# Certain values for company short name could be "CatchAll" which are not in MyACI so we search for them in CW to see if we can match.
zabbixCWCompanyID = cwapi.getCompanyIDbyIdentifier(zabbixCWCompany)
if not zabbixCWCompanyID:
    # Assign company as ChangeMe (default CW company) for ticket.
    zabbixCWCompanyID = cwapi.getCompanyIDbyIdentifier(defaultCompany)
    cwapi.writeDebugLog(f'Using default value for CompanyID.')
    zabbixTicketAdditionalMsg = zabbixTicketAdditionalMsg + "***NOTE:*** The specified company short name for this host " + zabbixCWCompany + " cannot be found.\r\n"
else:
    # My Adaptive Cloud company was found and mapped to Connectwise ID.
    cwapi.writeDebugLog(f'Using company ID from MyACI.')

    if cwapi.getCompanyDeletedStatusByID(zabbixCWCompanyID):
        cwapi.writeDebugLog(f'Company has been deleted in CW so using default value for CompanyID.')
        zabbixTicketAdditionalMsg = zabbixTicketAdditionalMsg + "***NOTE:*** The company short name found is deleted in CW so defaulting to " + defaultCompany + " for ticket creation.\r\n"
        zabbixCWCompanyID = cwapi.getCompanyIDbyIdentifier(defaultCompany)



# Get the new ticket status ID in CW to assign this ticket in CW.
zabbixCWNewTicketStatusId = cwapi.getServiceTicketBoardStatusDefaultStatus(f'{zabbixCWBoardId}', "Needs Assigned")

# Get closed ticket status ID from CW.
zabbixCWCloseStatusId = cwapi.getTicketBoardClosedStatusID(zabbixCWBoardId)

# Pull severity level of problem
zabbixSeverity = zabbixEventRecord[0]['severity']

# Get the hostname from Zabbix with the issue.
try:
    hostName = zabbixEventRecord[0]['hosts'][0]['host']
except Exception as e:
    cwapi.writeDebugLog(f'Exception Error Cant get hostname from event!\r\n{e}')
    zabbixTicketAdditionalMsg = zabbixTicketAdditionalMsg + "Cannot determine hostname for this event!\r\n"
    # zabbixErrorTicket("", "Cannot find hostname!", zabbixEventId, "Cannot determine hostname for this error from Zabbix.")
    hostName = "Unknown"

# Set the ticket subject for Connectwise:
zabbixCWTicketSubject = "Host: " + hostName + " Problem: " + zabbixEventRecord[0]['eventid'] + " " + zabbixEventRecord[0]['name']
zabbixCWTicketSubject = zabbixCWTicketSubject.replace('"', '').replace("'", '')
zabbixCWTicketSubject = jwzabbixapi.truncateStringMessage(zabbixCWTicketSubject)

if has_indices(zabbixAlertRecord):
    if zabbixAlertRecord:
        zabbixTicketDetail = zabbixAlertRecord[0]['message'].replace('NOTE:', '***NOTE:***')
    else:
        zabbixTicketDetail = 'No alert record found. \r\n'
else:
    zabbixTicketDetail = zabbixAlertRecord['message'].replace('NOTE:', '***NOTE:***')
zabbixEventLink = 'Zabbix Link: https://monitor.adaptivecloud.com/tr_events.php?triggerid=' + zabbixTriggerId + '&eventid=' + zabbixEventId + '\r\n'
zabbixTicketDetail = zabbixTicketDetail + zabbixEventLink

# Clean up the error message because quotes mess up the API.
zabbixCWTicketSubject = zabbixCWTicketSubject.replace('"', '').replace("'", '')

# Connectwise only allows 100 chars in subject, shorten if too long.
zabbixCWTicketSubject = jwzabbixapi.truncateStringMessage(zabbixCWTicketSubject)

# If there is no CW ticket board specified, do not generate a ticket, just exit.
if not zabbixCWBoard:
    cwapi.writeDebugLog('No CW board specified: Cannot/Will not generate a ticket.')
    jwzabbixapi.addMessageToProblem(zabbixEventId, 4, f"No CW board specified: Cannot/Will not generate a ticket.")
    exit(0)
    # No ticket generation because no variables passed.

cwapi.writeDebugLog(f'HOST: {zabbixHostName}  CWBOARD:{zabbixCWBoard} CWCOMPANY:{zabbixCWCompany}\r\nCWTICKETSUBJECT: {zabbixCWTicketSubject}')
cwapi.writeDebugLog(f'{zabbixEventLink}')


##### TICKET GENERATION / RESOLUTION BELOW! #####
if zabbixEventRecord:
    for event in zabbixEventRecord:
        if event['r_eventid'] == "0":  # Only consider current problems
            cwapi.writeDebugLog("This event is an active problem.")

            # Check to see if Zalert generated a ticket for this by searching the acknowledges in the event.
            result = check_for_ticket_created(zabbixTicketGenAckMsg, zabbixEventRecord)
            if result:
                cwapi.writeDebugLog("Ticket has already generated for this event.")

            else:
                # Check if problem is acknowledged, don't generate a ticket if it is.
                if zabbixEventRecord[0]['acknowledged'] == '1':
                    cwapi.writeDebugLog('Event has been acknowledged. We are not going to generate a ticket for this one.')
                    jwzabbixapi.addMessageToProblem(zabbixEventId, 4, f'This issue has been acknowledged before ticket creation. No ticket generation will occur.')
                    exit(0)

                # Ticket does not exist, create one.
                cwapi.writeDebugLog('No ticket for this event found, creating new ticket')
                # Connectwise severity mappings to Zabbix:
                match zabbixSeverity:
                    case '0':
                        cwImpact = 'Low'
                        cwUrgency = 'Low'
                    case '1':
                        cwImpact = 'Low'
                        cwUrgency = 'Low'
                    case '2':
                        cwImpact = 'Low'
                        cwUrgency = 'Medium'
                    case '3':
                        cwImpact = 'Medium'
                        cwUrgency = 'Medium'
                    case '4':
                        cwImpact = 'High'
                        cwUrgency = 'Medium'
                    case '5':
                        cwImpact = 'High'
                        cwUrgency = 'High'
                    case _:
                        cwImpact = 'Low'
                        cwUrgency = 'Low'

                ticketTemplate = {
                    "summary": zabbixCWTicketSubject,
                    "recordType": "ServiceTicket",
                    "severity": cwUrgency,
                    "impact": cwImpact,
                    "initialDescription": zabbixTicketAdditionalMsg + zabbixTicketDetail,
                    "board": {
                        "id": zabbixCWBoardId,
                    },
                    "status": {
                        "id": zabbixCWNewTicketStatusId,
                    },
                    "company": {
                        "id": zabbixCWCompanyID
                    }
                }

                # Ticket submission to CW:
                try:
                    # First attempt to create the ticket
                    # Uncomment out below if you want to test up till it generates a ticket but not create one.
                    # exit(0)
                    ticket_response = cwapi.postServiceTicket(ticketTemplate)

                    # Check to see we got a valid status code on the call to CW,
                    # if it's not 201 then something went wrong.
                    catchAllCompanyID = cwapi.getCompanyIDbyIdentifier(defaultCompany)
                    if ticket_response.status_code != 201 and ticketTemplate['company']['id'] != catchAllCompanyID:
                        # We have an error initially trying to post this ticket. We will try changing the company for the ticket to CatchAll as this is usually the cause of posting new tickets.
                        cwapi.writeDebugLog(f"Posting this ticket generated an API error: {ticket_response.json()['message']}")
                        cwapi.writeDebugLog(f"Trying with {defaultCompany} as the company..")
                        ticketTemplate['company'] = {"id": catchAllCompanyID}
                        zabbixTicketAdditionalMsg = zabbixTicketAdditionalMsg + "***NOTE*** Original company ID not accepted by CW, trying " + defaultCompany + " instead.\r\n"
                        ticketTemplate['initialDescription'] = zabbixTicketAdditionalMsg + zabbixTicketDetail
                        ticket_response = cwapi.postServiceTicket(ticketTemplate)
                        if ticket_response.status_code != 201:
                            zabbixErrorTicket("", "Ticket creation error!", zabbixEventId, ticket_response.json()['message'])
                            exit(1)

                    ticketID = ticket_response.json()['id']

                    # Write a message in the Zabbix event record giving the details of the CW ticket created.
                    if configEnv == 'TestEnv':
                        if zabbixTicketAdditionalMsg:
                            response = jwzabbixapi.addMessageToProblem(zabbixEventId, 4, zabbixTicketAdditionalMsg.replace('***NOTE:***', 'NOTE:'))

                    else:
                        if zabbixTicketAdditionalMsg:
                            response = jwzabbixapi.addMessageToProblem(zabbixEventId, 4, zabbixTicketAdditionalMsg.replace('***NOTE:***', 'NOTE:'))

                    # Add message in Zabbix event that we generated a ticket.
                    cwapi.writeDebugLog(zabbixTicketGenAckMsg.format_map(ticket_response.json()))
                    response = jwzabbixapi.addMessageToProblem(zabbixEventId, 4, zabbixTicketGenAckMsg.format_map(ticket_response.json()))

                except Exception as e:
                    cwapi.writeDebugLog(f'Failed to update Zabbix alert msg. Error: {e}')
                    cwapi.writeDebugLog(f'JSON response: {ticket_response.text}')
                    zabbixErrorTicket(e, "ticket form submission error", zabbixEventId, ticket_response.text)

        # Resolved problem, Zabbix will send a new alert on the resolved problems that got sent here, so we look for a ticket to close.
        else:
            cwapi.writeDebugLog("The event corresponds to a resolved problem, checking to see if there is a ticket to close.")

            # Check to see if Zalert generated a ticket for this by searching the acknowledges in the event.
            result = check_for_ticket_created(zabbixTicketGenAckMsg, zabbixEventRecord)
            # Result is True if there is a ticket note found in Zabbix.
            if not result:
                cwapi.writeDebugLog("No ticket generated for this event. Exiting.")
                exit(0)

            searchPattern = r"^.*Problem:\s*\d+"
            subjectSearch = re.search(searchPattern, zabbixCWTicketSubject).group(0)
            ticketToClose = cwapi.getOpenServiceTicketSearch(zabbixCWBoardId, subjectSearch)

            # Make sure we actually found a ticket:
            if not ticketToClose:
                cwapi.writeDebugLog("No ticket found in CW to close!")
                jwzabbixapi.addMessageToProblem(zabbixEventId, 4, f'No open ticket to close in CW for this problem.')
                exit(0)
            else:
                # Add a new ticket note saying it has been resolved.
                cwapi.writeDebugLog('Adding resolution message to ticket.')
                ticketClosingNote = jwzabbixapi.getAlertByEvent(zabbixEventRecord[0]['r_eventid'])
                cwapi.addNoteToTicket(ticketToClose[0]["id"], f"{ticketClosingNote[0]['message']}")

                # Close the ticket in CW
                cwapi.writeDebugLog(f'Trying to close Connectwise ticket: {ticketToClose[0]["id"]}')
                response = cwapi.closeServiceTicketByID(ticketToClose[0]["id"], zabbixCWCloseStatusId)

                if response.status_code == 200:
                    jwzabbixapi.addMessageToProblem(zabbixEventId, 4, zabbixTicketCloseAckMsg.format_map(ticketToClose[0]))
                    cwapi.writeDebugLog(zabbixTicketCloseAckMsg.format_map(ticketToClose[0]))
                else:
                    cwapi.writeDebugLog(f'CW Ticket failed to close!\r\nJSON Error:{response.text}')
else:
    cwapi.writeDebugLog("No event details found.")

cwapi.writeDebugLog("\r\n")
