# README.md
# Zabbix - Connectwise Interface in Python
This python script handles sending Zabbix problems to Connectwise tickets. Currently it will send Error level and above to Connectwise for ticket generation.

## Features

### **ConnectWise API Integration**
Provides comprehensive functionality to interact with ConnectWise for operations such as:
- Fetching company details based on identifiers (ID or name).
- Managing service tickets:
    - Creation
    - Retrieving statuses and closed IDs
    - Adding notes or closing tickets specifying the desired status.

- Handling service boards to retrieve or manipulate ticket-related workflows and statuses.
- Built-in support for **board and status searches**, ensuring precise control over service boards.

### **Zabbix API Integration**
Tested with Zabbix 6.4

Enables efficient management of Zabbix configurations and workflows:
- Retrieve detailed event/problem data driven by `event_id`.
- Add custom acknowledgment messages to Zabbix problems.
- Obtain global and host-specific macros, useful for dynamic configuration adjustments.
- Extend functionality with support for alerts, host groups, and custom tag-based insights:
    - Alert/event management (retrieving specific alerts or by trigger).
    - Dynamic Host Groups (list management, counts, and association).
    - Adding automated messages/actions linked to Zabbix alarms.


## Technical Highlights
- **Extensible Design**: Designed as separate modular classes, specialized for each API (`ConnectWiseApi`, `JWZabbix`).
- **Session-Based Networking**:
    - Efficient API calls using Python’s `requests` module with re-usable sessions.
    - Handles errors gracefully and logs debugging information for troubleshooting.

## Dependencies
- **Python Version**: 3.10 or higher
- **External Packages**:
    - `requests`: For handling HTTPS requests and responses.
    - `json`: For structured data transformation and serialization.
  - **Edit config file zapiconfig.json with your API tokens**
    - `TestEnv` contains the variables for a Connectwise test instance
    - `ProdEnv` contains variables for your prod instance.
    - If debug is set, it will log to /tmp/zalert.txt file.
