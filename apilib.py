#! /usr/bin/env python3
import requests
import json
from datetime import datetime

#######################################################################  CONNECTWISE API  ################################################
class ConnectWiseApi:

    def __init__(self, baseurl, clientid, company, publickey, privatekey, zDebug):
        self.baseurl = baseurl
        self.auth = (str(company) + '+' + str(publickey), str(privatekey))
        self.headers = {'clientID': clientid}
        self.agreementCache = {}
        self.zDebug = zDebug

    def _get(self, url, params=None):
        if params is None:
            params = {}
        params['pageSize'] = 1000
        session = requests.Session()
        response = session.get(url, params=params, headers=self.headers, auth=self.auth)
        return response

    def _put(self, url, **kwargs):
        session = requests.Session()
        response = session.put(url, headers=self.headers, auth=self.auth, **kwargs)
        return response

    def _patch(self, url, **kwargs):
        session = requests.Session()
        response = session.patch(url, headers=self.headers, auth=self.auth, **kwargs)
        return response

    def _post(self, url, **kwargs):
        session = requests.Session()
        response = session.post(url, headers=self.headers, auth=self.auth, **kwargs)
        return response

    def _delete(self, url, **kwargs):
        session = requests.Session()
        response = session.delete(url, headers=self.headers, auth=self.auth, **kwargs)
        return response

    def getCompanyByIdentifier(self, identifier, **kwargs):
        """
        :param identifier: The unique identifier for the company
        :param kwargs: Additional keyword arguments to filter the company details
        :return: The company details obtained from the API response
        """
        url = self.baseurl + '/company/companies'
        params = {
            'conditions': 'identifier=\"%s\"' % identifier,
            **kwargs,
        }
        return self._get(url, params=params)

    def getCompanyIDbyIdentifier(self, identifier):
        """
        :param identifier: A unique identifier, which can be either the ID or the name of the company.
        :return: The company ID if the identifier is found; otherwise, None.
        """
        url = self.baseurl + '/company/companies'
        params = {
            'conditions': f'identifier=\"{identifier}\" OR name=\"{identifier}\"'
        }
        response = self._get(url, params=params)

        if response:
            try:
                companyID = response.json()[0]['id']
                return companyID
            except (KeyError, IndexError):
                return None
        else:
            return None

    def getCompanyIdentifierByID(self, identifier):
        """
        :param identifier: The unique identifier for the company.
        :return: The company identifier corresponding to the given ID.
        """
        url = self.baseurl + '/company/companies'
        params = {
            'conditions': f'id={identifier}'
        }
        response = self._get(url, params=params)
        companyID = response.json()[0]['identifier']
        return companyID

    def getCompanyByID(self, identifier):
        """
        :param identifier: The unique identifier for the company.
        :return: The company identifier corresponding to the given ID.
        """
        url = self.baseurl + '/company/companies'
        params = {
            'conditions': f'id={identifier}'
        }
        response = self._get(url, params=params)
        companyInfo = response.json()[0]
        return companyInfo

    def getCompanyDeletedStatusByID(self, identifier):
        """
        :param identifier: The unique identifier for the company.
        :return: The company identifier corresponding to the given ID.
        """
        url = self.baseurl + '/company/companies'
        params = {
            'conditions': f'id={identifier}'
        }
        response = self._get(url, params=params)
        companyDeleted = response.json()[0]['deletedFlag']
        return companyDeleted

    def getServiceTicketBoardStatusDefaultStatus(self, boardId, statusName):
        """
        :param boardId: The identifier for the service board.
        :param statusName: The name of the status to check.
        :return: The identifier of the default status for the specified board and status name.
        """
        # print(f'boardId: {boardId}  statusName: {statusName}')
        url = self.baseurl + '/service/boards/' + str(boardId) + '/statuses'
        params = {'conditions': 'name="%s"' % statusName}
        response = self._get(url, params=params)

        # Check if the HTTP response was successful
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get service ticket board status. HTTP Status Code: {response.status_code}")

        try:
            jsonResponse = response.json()
            if not jsonResponse:
                raise ValueError("Empty JSON response")
            defaultStatus = jsonResponse[0]['id']
        except ValueError as e:
            raise RuntimeError(f"Failed to parse JSON response: {e}")
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Expected key not found in JSON response: {e}")

        return defaultStatus

    def getServiceTicketBoardIdFromName(self, boardName):
        """
        :param boardName: The name of the service ticket board to search for
        :return: The ID of the service ticket board if found, otherwise None
        """
        url = self.baseurl + '/service/boards'
        params = {
            'conditions': f'name="{boardName}"',
        }
        response = self._get(url, params=params)
        if response:
            # print(f'response: {response.text}')
            return response
        else:
            return None

    def getServiceTicketBoardIDStatuses(self, boardID):
        """
        :param boardID: ID of the service ticket board to fetch statuses for
        :return: JSON response containing statuses of the specified service ticket board
        """
        try:
            url = self.baseurl + '/service/boards/%d/statuses' % boardID
            return self._get(url)
        except Exception as e:
            self.zDebug(f'getServiceTicketBoardsStatuses error {e}')
            exit(0)

    def getTicketBoardClosedStatusID(self, boardID):
        """
        :param boardID: The ID of the service ticket board.
        :return: The ID of the closed status for the specified ticket board.
        """
        ticketStatuses = self.getServiceTicketBoardIDStatuses(boardID)
        closedID = ""
        for item in ticketStatuses.json():
            if item["name"][:7] == ">Closed" and not closedID:
                closedID = item["id"]
            # if item["name"] == ">Closed - No Automatic Email":
            if ">Closed" in item["name"] and "No" in item["name"] and "Email" in item["name"]:
                closedID = item["id"]
        return closedID

    def getTicketBoardStatusFromID(self, boardID, statusID):
        """
        This method retrieves the name of a service ticket board status given a boardID and statusID.

        Args:
            boardID (int): The ID of the service ticket board.
            statusID (int): The ID of the status within the service ticket board.

        Returns:
            str: The name of the status associated with the provided statusID.

        Raises:
            RuntimeError: If the HTTP response status code is not 200.
            RuntimeError: If parsing the JSON response fails or expected keys are missing.

        The method performs the following steps:
        1. Constructs the URL to access the status information based on the `boardID`.
        2. Sets the `conditions` parameter to filter the status by `statusID`.
        3. Sends a GET request to the ConnectWise API to retrieve the status information.
        4. Extracts the status name from the JSON response and returns it.
        5. If the HTTP response is not successful (status code != 200), raises a `RuntimeError`.
        6. Tries to parse the JSON response and handle any parsing errors.
        """

        url = self.baseurl + '/service/boards/' + str(boardID) + '/statuses'
        params = {'conditions': 'id=%s' % statusID}
        response = self._get(url, params=params)

        # Check if the HTTP response was successful
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to get service ticket board status. HTTP Status Code: {response.status_code}")

        try:
            jsonResponse = response.json()
            if not jsonResponse:
                raise ValueError("Empty JSON response")
            defaultStatus = response.json()[0]['name']
        except ValueError as e:
            raise RuntimeError(f"Failed to parse JSON response: {e}")
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Expected key not found in JSON response: {e}")

        return defaultStatus

    def postServiceTicket(self, ticketSummary):
        """
        :param ticketSummary: Summary of the service ticket to be created, typically a dictionary containing ticket details.
        :return: Response from the POST request indicating the result of the service ticket creation.
        """
        url = self.baseurl + '/service/tickets'
        return self._post(url, json=ticketSummary)

    def getServiceTicketId(self, ticketid):
        """
        :param ticketid: The unique identifier for the service ticket.
        :return: The details of the service ticket retrieved from the specified URL.
        """
        url = self.baseurl + '/service/tickets/%d' % ticketid
        return self._get(url)

    # def getServiceTicketSearch(self, boardID, messageText):
    #     """
    #     param boardID: The identifier for the service board to search within.
    #     param messageText: The text of the message to search for within ticket summaries.
    #     :return: A list of tickets found that match the search criteria or None if no tickets are found.
    #     """
    #     url = self.baseurl + '/service/tickets'
    #     params = {
    #         'conditions': f'summary=="{messageText}"'
    #     }
    #     ticketsFound = self._get(url, params=params).json()
    #     if ticketsFound:
    #         #print("Ticket Found: %s" % ticketsFound[0])
    #         return ticketsFound
    #     else:
    #         #print("No Ticket Found")
    #         return None

    def getOpenServiceTicketSearch(self, boardID, messageText):
        """
        :param boardID: The unique identifier of the service board where tickets are searched.
        :param messageText: The text to be searched at the beginning of the ticket summaries.
        :return: A list of open service tickets matching the search criteria, or None if no tickets are found.
        """
        url = self.baseurl + '/service/tickets'
        params = {
            'conditions': f'board/id = {boardID} AND summary like "{messageText}%" AND status/name not like ">Closed%"'
        }
        ticketsFound = self._get(url, params=params).json()

        if ticketsFound:
            return ticketsFound
        else:
            return

    def closeServiceTicketByID(self, ticketID, ticketClosedStatusId):
        """
        :param ticketID: ID of the service ticket to be closed
        :param ticketClosedStatusId: Status identifier to mark the ticket as closed
        :return: Response object from the API call to close the ticket
        """
        ticketPatch = [{
            'op': 'replace',
            'path': 'status/id',
            'value': ticketClosedStatusId,
        }]
        url = self.baseurl + '/service/tickets/%d' % ticketID
        response = self._patch(url, json=ticketPatch)
        return response

    def addNoteToTicket(self, ticketId, ticketNote, internalFlag=True):
        """
        :param ticketId: The ID of the ticket to which the note should be added
        :param ticketNote: The text of the note to be added to the ticket
        :param internalFlag: Specifies whether the note is internal (default is True)
        :return: The response from the server after attempting to add the note to the ticket
        """
        url = f'{self.baseurl}/service/tickets/{ticketId}/notes'

        payload = {
            "text": ticketNote,
            "ticketId": ticketId,
            "internalFlag": internalFlag,
            "detailDescriptionFlag": True,
            "internalAnalysisFlag": False,
            "resolutionFlag": False,
            "issueFlag": False,
            "dateCreated": datetime.now().isoformat(),
            "createdBy": "zabbix"
        }
        response = self._post(url, json=payload)
        return response

    def writeDebugLog(self, messageText):
        """
        :param messageText: The debug message text to be written to the log file.
        :return: None
        """
        if self.zDebug:
            f = open('/tmp/zalert.txt', 'a')
            f.write(f'{messageText}\n')
            f.close()


#######################################################################  ZABBIX API #######################################################################
class JWZabbix:

    def __init__(self, zURL, zAPIKey, zDebug):
        self.zURL = zURL
        self.zAPIKey = zAPIKey
        self.agreementCache = {}
        self.zDebug = zDebug

    def zabbixAPIRequest(self, method, params):
        """
        :param method: The name of the Zabbix API method to be called.
        :param params: The parameters to be passed to the Zabbix API method.
        :return: The JSON response from the Zabbix API.

        """
        headers = {
            'Content-Type': 'application/json-rpc',
            'Authorization': f'Bearer {self.zAPIKey}'  # Use the API token for authentication
        }
        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': 1
        }
        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))
        return response.json()

    def truncateStringMessage(self, s, max_length=100):

        if len(s.encode('utf-8')) <= max_length:
            return s
        else:
            return s[:70] + "..."  # Add an ellipsis to indicate truncation

    # Function to get all non-active events
    def getNonActiveEventsById(self, event_id):
        """
        :param event_id: The unique identifier of the event to be retrieved.
        :return: JSON response containing details of the non-active (resolved) event.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "event.get",
            "params": {
                "eventids": event_id,
                "output": "extend",
                "value": 1  # 1 indicates resolved events, 0 indicates active events
            },
            "id": 2,
            "auth": self.zAPIKey
        }
        headers = {
            'Content-Type': 'application/json-rpc'
        }
        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))
        return response.json()

    def getEventByEventId(self, event_id):
        """
        :param event_id: The unique identifier of the event to retrieve.
        :return: A dictionary containing the event details, including hosts, acknowledges, tags, and suppression data.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "event.get",
            "params": {
                "eventids": event_id,
                "selectHosts": "extend",
                "output": "extend",
                "select_acknowledges": "extend",
                "selectTags": "extend",
                "selectSuppressionData": "extend"
            },
            "id": 1,
            "auth": self.zAPIKey
        }
        headers = {
            'Content-Type': 'application/json-rpc'
        }
        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))
        return response.json()['result']

    def addMessageToProblem(self, event_id, action, message):
        """
        :param event_id: The identifier of the event to which the message will be added.
        :param action: The action type that is being acknowledged.
        :param message: The message content that needs to be added to the problem.
        :return: None
        """
        message = self.truncateStringMessage(message, 1000)
        payload = {
            'jsonrpc': '2.0',
            'method': 'event.acknowledge',
            'params': {
                'eventids': [event_id],
                'message': message,
                'action': action
            },
            'auth': self.zAPIKey,
            'id': 1
        }

        response = requests.post(self.zURL, headers={'Content-Type': 'application/json-rpc'}, data=json.dumps(payload))
        result = response.json()
        return result


    def getGlobalMacro(self, macro_id):
        """
        :param macro_id: The identifier for the desired global macro.
        :return: The value of the global macro if found, otherwise None.
        """
        # Get global macros
        payload = {
            "jsonrpc": "2.0",
            "method": "usermacro.get",
            "params": {
                "globalmacro": True,  # to get global macros
            },
            "auth": self.zAPIKey,
            "id": 1
        }
        response = requests.post(self.zURL, headers={'Content-Type': 'application/json-rpc'}, data=json.dumps(payload))
        result = response.json()
        for item in result['result']:
            if item['macro'] == macro_id:
                return item['value']
                # macro = item['value']
        return None


    def getHostMacros(self, host_id):
        """
        :param host_id: The identifier of the host for which to retrieve macros.
        :return: A list of macros associated with the specified host.
        """
        # Get specific macros from the host.
        payload = {
            "jsonrpc": "2.0",
            "method": "usermacro.get",
            "params": {
                "hostids": host_id
            },
            "auth": self.zAPIKey,
            "id": 3
        }

        response = requests.post(self.zURL, headers={'Content-Type': 'application/json-rpc'}, data=json.dumps(payload))
        result = response.json()


        return result['result']

    def getMacroValue(self, json_data, macro_name):
        """
        :param json_data: event data in JSON format.
        :param macro_name: the name of the macro for which we want the value.
        :return: the value of the specified macro if found, otherwise None.
        """
        # This function gets the macro's for a specific host. The host
        # json_data = event data in JSON format.
        # macro_name = the name of the macro we want the value for.
        json_data = json.loads(json_data)

        for item in json_data:
            macro = item['macro']
            value = item['value']
            if item.get('macro') == macro_name:
                return value
        return None

    def getAlertByEvent(self, event_id):
        """
        :param event_id: The ID of the event for which to retrieve alert details.
        :return: The alert details for the specified event if successful; otherwise, None.
        """
        # Get alert details for an event.

        headers = {
            'Content-Type': 'application/json-rpc'
        }

        data = {
            "jsonrpc": "2.0",
            "method": "alert.get",
            "params": {
                "output": "extend",
                "eventids": event_id,
                "selectAcknowledges": "extend"
            },
            "auth": self.zAPIKey,
            "id": 1
        }
        data = json.dumps(data)
        response = requests.post(self.zURL, headers=headers, data=data)
        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                return result['result']
            else:
                self.writeDebugLog(f'No alerts found for the given event ID')
                return None
        else:
            self.writeDebugLog(f'Error: {response.status_code}')
            return None

    def getAlertMessageByEvent(self, event_id):
        """
        :param event_id: The ID of the event for which alert details are to be fetched.
        :return: The alert message for the given event ID if available, else None.
        """
        # Get alert details for an event.

        payload = {
            "jsonrpc": "2.0",
            "method": "alert.get",
            "params": {
                "eventids": event_id,
                "output": "extend",
                "selectMediatypes": "extend"
            },
            "auth": self.zAPIKey,
            "id": 3
        }

        alert_data = requests.post(self.zURL, headers={'Content-Type': 'application/json-rpc'}, data=json.dumps(payload)).json()['result']

        if alert_data:
            alert_message = json.dumps(alert_data[0]['message'])
            return alert_message
        else:
            return None

    def getAlertById(self, alert_id):
        """
        :param alert_id: The ID of the alert to fetch information for.
        :return: The alert information if found, otherwise None.
        """
        # Get alert info from alert id. The id will be passed by Zabbix to the script.
        # Not used in code, for debug purposes.
        headers = {
            'Content-Type': 'application/json-rpc'
        }

        data = {
            "jsonrpc": "2.0",
            "method": "alert.get",
            "params": {
                "alertids": alert_id,
                "output": "extend",
                "selectHosts": "extend",
                "selectTriggers": "extend",
                "selectEvents": "extend"
            },
            "auth": self.zAPIKey,
            "id": 1
        }

        response = requests.post(self.zURL, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                return result['result']
            else:
                print("No such alert found")
                return None
        else:
            print("Error: ", response.status_code)
            return None


    def getAlertDetails(self, alertid):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.zAPIKey}'
        }
        payload = {
            "jsonrpc": "2.0",
            "method": "alert.get",
            "params": {
                "alertids": alertid,
                "output": "extend",
                "selectHosts": "extend",
                "selectTriggers": "extend",
                "selectEvents": "extend"
            },
            "auth": self.zAPIKey,
            "id": 2
        }
        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))
        result = response.json()
        return result['result']

    def getHostCountForGroup(self, groupID):
        payload = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "output": ["hostid"],
                "groupids": groupID,
                "countOutput": True
            },
            "auth": self.zAPIKey,
            "id": 1
        }
        headers = {
            'Content-Type': 'application/json-rpc'
        }
        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))
        return response.json()

    def getGroupsForHost(self, hostid):
        headers = {
            "Content-Type": "application/json-rpc",
            'Authorization': f'Bearer {self.zAPIKey}'
        }

        # Create the payload for retrieving host groups
        payload = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "output": ["hostid"],
                "selectGroups": ["groupid", "name"],
                "filter": {
                    "hostid": [
                        hostid
                    ]
                }
            },
            "id": 1,
            "auth": None
        }
        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))
        data = response.json()

        # Check if the request was successful
        if 'result' in data:
            host_groups = data['result']
            if host_groups:
                return data
            else:
                return
                # No groups found for host '{hostid}'
        else:
            return
            # Error in API request:", data.get('error', 'Unknown error')



    def getAllHostGroups(self):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.zAPIKey}'
        }

        payload = {
            "jsonrpc": "2.0",
            "method": "hostgroup.get",
            "params": {
                "output": "extend"
            },
            "id": 1,
            "auth": None  # Using token-based authentication
        }
        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                return result['result']
            else:
                raise ValueError("Invalid response from Zabbix API: 'result' not found")
        else:
            raise Exception(f"Failed to retrieve host groups: {response.status_code}, {response.text}")

    def getHost(self, hostid):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.zAPIKey}'
        }

        payload = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "hostids": hostid,
                "output": "extend"
            },
            "id": 1,
            "auth": None  # Using token-based authentication
        }
        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                return result['result']
            else:
                raise ValueError("Invalid response from Zabbix API: 'result' not found")
        else:
            raise Exception(f"Failed to retrieve host groups: {response.status_code}, {response.text}")

    def billingTagCounts(self):
        headers = {'Content-Type': 'application/json'}
        payload = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "output": ["hostid"],
                'selectTags': 'extend'
            },
            "auth": self.zAPIKey,
            "id": 1
        }

        response = requests.post(self.zURL, headers=headers, data=json.dumps(payload))
        response_json = response.json()

        if 'error' in response_json:
            raise Exception(f"Zabbix API error: {response_json['error']}")

        return response_json['result']


    def writeDebugLog(self, messageText):
        if self.zDebug:
            f = open('/tmp/zalert.txt', 'a')
            f.write(f'{messageText}\n')
            f.close()


    def rename_host_group(self, old_group_name, new_group_name):
        """
        Renames a Zabbix host group using the Zabbix API.
        :param old_group_name: The current name of the host group
        :param new_group_name: The new name for the host group
        :return: True if the renaming was successful, else False
        """

        # Define the headers and the API endpoint
        headers = {'Content-Type': 'application/json-rpc'}

        # Step 1: Get the host group ID by the old name
        get_group_payload = {
            "jsonrpc": "2.0",
            "method": "hostgroup.get",
            "params": {
                "filter": {
                    "name": old_group_name
                }
            },
            "auth": self.zAPIKey,
            "id": 1
        }

        try:
            response = requests.post(self.zURL, headers=headers, data=json.dumps(get_group_payload))
            result = response.json()

            if 'error' in result:
                # Error fetching host group: {result['error']}
                return False

            # Ensure that the host group exists
            if len(result['result']) == 0:
                # Host group '{old_group_name}' not found.
                return False

            # Get the group ID of the old host group
            group_id = result['result'][0]['groupid']

            # Step 2: Update the host group name
            update_group_payload = {
                "jsonrpc": "2.0",
                "method": "hostgroup.update",
                "params": {
                    "groupid": group_id,
                    "name": new_group_name
                },
                "auth": self.zAPIKey,
                "id": 1
            }

            update_response = requests.post(self.zURL, headers=headers, data=json.dumps(update_group_payload))
            update_result = update_response.json()

            if 'error' in update_result:
                # Error updating host group: {update_result['error']}
                return False

            # Host group '{old_group_name}' renamed to '{new_group_name}' successfully.
            return True

        except requests.exceptions.RequestException:
            # Request error: {e}
            return False

    def getHostTagsByHostId(self, host_id):
        # This function returns all host tags for a named host in Zabbix.
        headers = {
            'Content-Type': 'application/json-rpc',
            'Authorization': f'Bearer {self.zAPIKey}'
        }
        tags_request_data = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "output": ["hostid"],
                "selectTags": "extend",  # Get all tags for the host
                "hostids": host_id
            },
            "auth": None,
            "id": 2
        }

        response = requests.post(self.zURL, headers=headers, json=tags_request_data)

        if response.status_code != 200:
            # "Error retrieving tags for host '{host_id}'.
            return []
        # Parse and return the tags
        tags = response.json().get('result', [])[0].get('tags', [])
        return tags
