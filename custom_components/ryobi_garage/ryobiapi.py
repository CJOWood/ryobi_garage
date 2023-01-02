import asyncio
import json
import logging
import threading
from typing import Dict

import httpx
import websocket

_LOGGER = logging.getLogger(__name__)

# Socket
SOCK_CONNECTED = "Open"
SOCK_CLOSE = "Close"
SOCK_ERROR = "Error"
# API Answer
SUCCESS_OK = "success"
SERVICE_ERROR = "ServiceErrorException"
USER_NOT_EXIST = "UserNotExist"
PASSWORD_NOK = "PasswordInvalid"
# WSS Messages
GARAGE_UPDATE_MSG = "wskAttributeUpdateNtfy"
WS_AUTH_OK = "authorizedWebSocket"
WS_CMD_ACK = "result"
WS_OK = "OK"

# API
RYOBI_URL = "tti.tiwiconnect.com"
HTTP_URL = f"https://{RYOBI_URL}"
WS_URL = f"wss://{RYOBI_URL}"
HTTP_ENDPOINT = f"{HTTP_URL}/api"
WS_ENDPOINT = f"{WS_URL}/api/wsrpc"
N_RETRY = 5
WS_RETRY = 10
ACK_TIMEOUT = 5
HTTP_TIMEOUT = 5


class RyobiApi:
    """
    Ryobi API
    Handle connexion with Ryobi's server to get WSS credentials
    """

    def __init__(self, username, password):
        _LOGGER.debug("RyobiApi __init__")

        self.username = username
        self.password = password

        self.api_key = None
        self.user_id = None
        self.devices = []

    async def login(self, url=f"{HTTP_ENDPOINT}/login") -> bool:
        """ "
        Login to Ryobi platform
        """
        _LOGGER.debug("RyobiApi try login")

        params = {"username": self.username, "password": self.password}

        headers = {
            "host": RYOBI_URL,
            "content-type": "application/json",
        }

        resp = await self.send_http(url, params, headers)

        if "_id" in resp["result"]:
            self.user_id = resp["result"]["_id"]

            if "apiKey" in resp["result"]["auth"]:
                self.api_key = resp["result"]["auth"]["apiKey"]
            else:
                _LOGGER.error(
                    "RyobiApi: Could not get Api Key from server response: %s", resp
                )
                return False

            _LOGGER.debug("RyobiApi: Login successful. Id and Api Key retrieved")
            return True
        else:
            _LOGGER.error(
                "RyobiApi: Something went wrong with login, no user id found. See server response: %s",
                resp,
            )
            return False

    async def get_devices(self, url=f"{HTTP_ENDPOINT}/devices"):
        """
        Get device list registered from Ryobi server
        """
        _LOGGER.debug("RyobiApi get list of devices")

        params = {"username": self.username, "password": self.password}

        headers = {
            "host": RYOBI_URL,
            "content-type": "application/json",
        }

        resp = await self.send_http(url, params, headers, "GET")

        if resp:  # list not empty
            for result in resp["result"]:
                device = {}
                device["username"] = self.username
                device["password"] = self.password
                device["api_key"] = self.api_key
                device["u_id"] = self.user_id

                #get moduleId and portId

                device["type_ids"] = result["deviceTypeIds"]
                device["d_id"] = result["varName"]
                device["name"] = result["metaData"]["name"]
                device["version"] = result["metaData"]["version"]
                device["description"] = result["metaData"]["description"]
                device["last_seen"] = result["metaData"]["sys"]["lastSeen"]

                self.devices.append(device)

            _LOGGER.debug(
                "RyobiApi: Get device list OK. %s devices found", len(self.devices)
            )
            return self.devices
        else:
            _LOGGER.error("RyobiApi: FAILED to get device list: %s", resp)
            return []

    async def get_device(self, d_id, d_url=f"{HTTP_ENDPOINT}/devices"):
        """ Get state of specific device from Ryobi HTTP Server """
        _LOGGER.debug("Ryopbi Api: Retrieving device information for %s. ", d_id)

        url = f"{d_url}/{d_id}"
        params = {"username": self.username, "password": self.password}
        headers = {
            "host": RYOBI_URL,
            "content-type": "application/json",
        }

        resp = await self.send_http(url, params, headers, "GET")

        if resp:  # list not empty
            return self.extract_device_info(resp)
        else:
            _LOGGER.error("RyobiApi: Could not get information for that device. Returning nothing. ")

        return {"garage_state": None, "serial": None, "mac": None}

    def extract_device_info(self, response):
        """ Extract device information from get_device response """
        _LOGGER.debug("RyobiApi: Extracting device info. ")
        device_info = {}

        first_result = response["result"][0]

        #From masterUnit module
        master_unit = first_result["deviceTypeMap"]["masterUnit"]["at"]
        device_info["serial"] = master_unit["serialNumber"]["value"]
        device_info["mac"] = master_unit["macAddress"]["value"]

        deviceMap = first_result["deviceTypeMap"]

        #find the module that contains the garageDoor
        for module in deviceMap:
            if module.startswith('modulePort_'):
                if any("garageDoor" in sub for sub in deviceMap[module]["at"]["moduleProfiles"]["value"]):
                    device_info["module_id"] = deviceMap[module]["at"]["moduleId"]["value"]
                    port = device_info["port_id"] = deviceMap[module]["at"]["portId"]["value"]
                    break

        garage_door = first_result["deviceTypeMap"][f"garageDoor_{port}"]["at"]
        garage_light = first_result["deviceTypeMap"][f"garageLight_{port}"]["at"]

        device_info["garage_state"] = {
            "vacationMode": {
                "lastValue": garage_door["vacationMode"]["lastValue"],
                "value": garage_door["vacationMode"]["value"],
                "vacation_state": garage_door["vacationMode"]["enum"][garage_door["vacationMode"]["value"]], #TODO Eventually define enum in const so we dont rely on server response to define enum
            },
            "sensorFlag": {
                "lastSet": garage_door["sensorFlag"]["lastSet"],
                "lastValue": garage_door["sensorFlag"]["lastValue"],
                "value": garage_door["sensorFlag"]["value"],
            },
            "opMode": {
                "lastSet": garage_door["opMode"]["lastSet"],
                "lastValue": garage_door["opMode"]["lastValue"],
                "value": garage_door["opMode"]["value"],
                "op_state": garage_door["opMode"]["enum"][garage_door["opMode"]["value"]] #TODO Eventually define enum in const so we dont rely on server response to define enum
            },
            "doorState": {
                "lastSet": garage_door["doorState"]["lastSet"],
                "lastValue": garage_door["doorState"]["lastValue"],
                "value": garage_door["doorState"]["value"],
                "enum": garage_door["doorState"]["enum"],
                "state": garage_door["doorState"]["enum"][garage_door["doorState"]["value"]] #TODO Eventually define enum in const so we dont rely on server response to define enum
            },
            "doorPercentOpen": garage_door["doorPercentOpen"]["value"], #-1 is closed
            "doorPosition": {
                "lastSet": garage_door["doorPosition"]["lastSet"],
                "lastValue": garage_door["doorPosition"]["lastValue"],
                "value": garage_door["doorPosition"]["value"], #value of 0 - 180 -> but not?? Could be different per door?
            },
            "garageLight": {
                "lightState": {
                    "lastSet": garage_light["lightState"]["lastSet"],
                    "lastValue": garage_light["lightState"]["lastValue"],
                    "value": garage_light["lightState"]["value"],
                },
                "lightTimer": {
                    "lastSet": garage_light["lightTimer"]["lastSet"],
                    "lastValue": garage_light["lightTimer"]["lastValue"],
                    "value": garage_light["lightTimer"]["value"],
                },
            }
        }

        return device_info

    @staticmethod
    async def send_http(url, params, headers, method="POST"):
        """
        Send HTTP request
        """
        _LOGGER.debug("Send HTTP request Url=%s Params=%s", url, params)
        timeout = httpx.Timeout(HTTP_TIMEOUT, connect=15.0)
        request = httpx.Request(method, url, params=params, headers=headers)
        for attempt in range(N_RETRY):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.send(request)
                    if resp.status_code == 200:
                        # Server status OK
                        _LOGGER.debug("RyobiApi: Send HTTP OK, return=200")
                        _LOGGER.debug("RyobiApi: HTTP data received = %s", resp.json())
                        return resp.json()
                    elif resp.status_code == 401:
                        _LOGGER.error(
                            "RyobiApi: Invlaid login credentials. HTTP 401 Unauthorized. Skipping retry"
                        )
                        return {
                            "msg": "error",
                            "details": "Invalid login credentials HTTP 401 Unothorized. Skipped retry",
                        }
                    else:
                        # Server status NOK
                        _LOGGER.warning(
                            "RyobiApi: Bad server response (status code=%s) retry... (%s/%s)",
                            resp.status_code,
                            attempt,
                            N_RETRY,
                        )
            except httpx.RequestError as err:
                _LOGGER.debug(
                    "Send HTTP exception details=%s retry... (%s/%s)",
                    err,
                    attempt,
                    N_RETRY,
                )

        _LOGGER.error("RyobiApi: HTTP error after %s retry", N_RETRY)
        return {"msg": "error", "details": f"Failed after {N_RETRY} retry"}


class RyobiWssCtrl(RyobiApi):
    """
    Ryobi Websocket Controller
    Handle websocket to send/recieve garage door control and information
    """

    def __init__(self, username, password, api_key, u_id, d_id):
        super().__init__(username, password)
        _LOGGER.debug("RyobiApi WSS Control __init__")

        self.socket_state = SOCK_CLOSE
        self.subscriber = []
        self.wst = None
        self.ws = None
        self._refresh_time = 60
        self.sent_counter = 0

        self.garage_state = {}
        self.api_key = api_key
        self.device_id = d_id

    async def check_credentials(self):
        """
        Check if credentials for WSS are OK
        """
        _LOGGER.debug("RyobiApi (WSS) Checking credentials")
        if not self.api_key:
            _LOGGER.debug("RyobiApi (WSS) api key needed")
            if await self.login():
                return True
            else:
                return False
        _LOGGER.debug("RyobiApi (WSS) api_key are OK")
        return True

    async def open_wss_thread(self):
        """
        Connect WebSocket to Ryobi Server and create a thread to maintain connection alive
        """
        if not await self.check_credentials():
            _LOGGER.error("RyobiApi (WSS) Failed to obtain WSS Api Key")
            return False

        _LOGGER.debug("RyobiApi (WSS) Addr=%s / Api Key=%s", WS_ENDPOINT, self.api_key)

        try:
            self.ws = websocket.WebSocketApp(
                WS_ENDPOINT,
                header={
                    "Connection": "keep-alive, Upgrade",
                    "handshakeTimeout": "10000",
                },
                on_message=self.on_message,
                on_close=self.on_close,
                on_open=self.on_open,
                on_error=self.on_error,
                on_pong=self.on_pong,
            )

            self.wst = threading.Thread(target=self.ws.run_forever)
            self.wst.start()

            if self.wst.is_alive():
                _LOGGER.debug("RyobiApi (WSS) Thread was init")
                return True
            else:
                _LOGGER.error("RyobiApi (WSS) Thread connection init has FAILED")
                return False

        except websocket.WebSocketException as err:
            self.socket_state = SOCK_ERROR
            _LOGGER.debug("RyobiApi (WSS) Error while opening socket: %s", err)
            return False

    async def authenticate_with_server(self):
        """Authenticate with Ryobi Websocket using username and Api Key"""
        _LOGGER.debug("RyobiApi (WSS) Attempting to authenticate with websocket. ")
        await self.publish_wss(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "srvWebSocketAuth",
                "params": {"varName": self.username, "apiKey": self.api_key},
            }
        )

    async def subscribe_to_notifications(self, d_id):
        """RyobiApi (WSS) Subscribe to notifications for devices in list"""
        _LOGGER.debug("RyobiApi (WSS) Subscribing to notifications for %s. ", d_id)
        await self.publish_wss(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "wskSubscribe",
                "params": {"topic": d_id + ".wskAttributeUpdateNtfy"},
            }
        )

        self.garage_state["is_available"] = True
        self._call_subscriber()
        return True

    async def connect_wss(self):
        """Connect to websocket"""
        if self.socket_state == SOCK_CONNECTED:
            _LOGGER.debug("RyobiApi (WSS) Already connected... ")
            return True

        _LOGGER.debug("RyobiApi (WSS) Not connected, connecting")

        if await self.open_wss_thread():
            _LOGGER.debug("RyobiApi (WSS) Connecting")
        else:
            return False

        for i in range(WS_RETRY):
            _LOGGER.debug("RyobiApi (WSS) awaiting connection established... %s", i)
            if self.socket_state == SOCK_CONNECTED:
                await self.authenticate_with_server()
                await asyncio.sleep(0.5)
                await self.subscribe_to_notifications(self.device_id)
                return True
            await asyncio.sleep(0.5)
        return False

    def on_error(self, ws, error):
        """Socket "On_Error" event"""
        details = ""
        if error:
            details = f"(details : {error})"
        _LOGGER.debug("RyobiApi (WSS) Error: %s", details)
        self.socket_state = SOCK_ERROR

    def on_close(self, ws, close_status_code, close_msg):
        """Socket "On_Close" event"""
        _LOGGER.debug("RyobiApi (WSS) Closed")

        if close_status_code or close_msg:
            _LOGGER.debug(
                "RyobiApi (WSS) Close Status_code: %s", str(close_status_code)
            )
            _LOGGER.debug("RyobiApi (WSS) Close Message: %s", str(close_msg))
        self.socket_state = SOCK_CLOSE

    def on_pong(self, message):
        """Socket on_pong event"""
        _LOGGER.debug("RyobiApi (WSS) Got a Pong")

    def on_open(self, ws):
        """Socket "On_Open" event"""
        _LOGGER.debug("RyobiApi (WSS) Connection established OK")
        self.socket_state = SOCK_CONNECTED

    def on_message(self, ws, msg):
        """Socket "On_Message" event"""
        self.sent_counter = 0
        message = json.loads(msg)
        _LOGGER.debug("RyobiApi (WSS) Msg received %s", message)

        # TODO deal with incoming messages and updates
        if 'method' in message:
            if message["method"] == GARAGE_UPDATE_MSG:
                _LOGGER.debug("RyobiApi (WSS) recieved garage door update message. ")
                if "params" in message:
                    self.parse_device_update(message["params"])
                    self._call_subscriber()

            elif message["method"] == WS_AUTH_OK:
                if message["params"]["authorized"]:
                    _LOGGER.debug("RyobiApi (WSS) Msg: Api Key? authorization OK. ")
                else:
                    _LOGGER.error("RyobiApi (WSS) Msg: Api Key? not authorized based on response form server. ")

        elif 'result' in message:
            if 'result' in message["result"]:
                if message[WS_CMD_ACK]["result"] == WS_OK:
                    _LOGGER.debug("RyobiApi (WSS) Msg: Recieved OK result from server. ")
            if 'authorized' in message[WS_CMD_ACK]:
                if message[WS_CMD_ACK]['authorized']:
                    _LOGGER.debug("RyobiApi (WSS) Msg: User? authorization OK. ")
        else:
            _LOGGER.error(
                "RyobiApi (WSS) Received an unknown message from server: %s}", message
            )

    def parse_device_update(self, update):
        """ Parse the device update message from websocket and update object with values. """
        if self.device_id != update["varName"]:
            _LOGGER.debug("RyobiApi (WSS): Recieved update for a differnt device! (%s but I am %s)", update["varName"], self.device_id)
            return None

        for key in list(update.keys()):
            if key == "topic" or key == "varName" or key == "id":
                continue

            _LOGGER.debug("RyobiApi (WSS) parse update each item in %s: %s", key, update[key])

            module_name = key.split(".")[1]

            if "garageDoor" in key:
                for item in update[key]:
                    self.garage_state[module_name][item] = update[key][item]

            elif "garageLight" in key:
                for item in update[key]:
                    self.garage_state["garageLight"][module_name][item] = update[key][item]

            else:
                _LOGGER.error("RyobiApi (WSS) parse update: Did not recognized module: %s", key)


    async def publish_wss(self, dict_message):
        """
        Publish payload over WSS connexion
        """
        json_message = json.dumps(dict_message)
        _LOGGER.debug("RyobiApi (WSS) Publishing message : %s", json_message)

        if self.sent_counter >= 5:
            _LOGGER.warning(
                "RyobiApi (WSS) Link is UP, but server has stopped answering request. "
            )
            self.sent_counter = 0
            self.ws.close()
            self.socket_state = SOCK_CLOSE

        for attempt in range(N_RETRY):
            if self.socket_state == SOCK_CONNECTED:
                try:
                    self.ws.send(json_message)
                    self.sent_counter += 1
                    _LOGGER.debug("RyobiApi (WSS) Msg published OK (%s)", attempt)
                    return True
                except websocket.WebSocketConnectionClosedException as err:
                    self.socket_state = SOCK_CLOSE
                    _LOGGER.debug(
                        "RyobiApi (WSS) Error while publishing message (details: %s)",
                        err,
                    )
            else:
                _LOGGER.debug(
                    "RyobiApi (WSS) Can't publish message socket_state= %s, reconnecting... ",
                    self.socket_state,
                )
                await self.connect_wss()

        _LOGGER.error(
            "RyobiApi (WSS) Failed to puslish message after %s retry. ", N_RETRY
        )
        return False

    async def send_command(self, command):
        """
        Send command to websocket
        """
        _LOGGER.debug(
            "RyobiApi (WSS) send_command: %s to garage_door: %s",
            command,
            self.device_id
        )

        await self.publish_wss(command)

    async def refresh_handler(self, d_id):
        """This makes sure the websocket is connected every refresh_time interval"""
        _LOGGER.debug("RyobiApi (WSS) Start refresh_handler")
        while True:
            try:
                if self.socket_state != SOCK_CONNECTED:
                    await self.connect_wss()

                await asyncio.sleep(self._refresh_time)
            except Exception as err:
                _LOGGER.error(
                    "RyobiApi (WSS) Error during refresh_handler (details=%s)", err
                )

    def subscribe(self, subscriber):
        """Subscribe to messages?"""
        _LOGGER.debug("RyobiApi (WSS): adding a new subscriber")
        self.subscriber.append(subscriber)

    def _call_subscriber(self):
        """Call subscriber on messge??"""
        _LOGGER.debug("RyobiApi (WSS): Calling subscriber (schedule_update_ha_state)")
        for subscriber in self.subscriber:
            subscriber(self)
