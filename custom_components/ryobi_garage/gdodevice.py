import logging

from .ryobiapi import RyobiWssCtrl
from .const import (WS_CMD_COVER_CLOSE, WS_CMD_COVER_OPEN, WS_CMD_LIGHT_OFF, WS_CMD_LIGHT_ON, WS_CMD_SET_POS)

_LOGGER = logging.getLogger(__name__)


class GdoDevice(RyobiWssCtrl):
    """
    A representation of the Ryobi Device to listen to WS.
    """

    def __init__(
        self,
        username,
        password,
        api_key,
        u_id,
        d_id,
        name,
        description,
        module_id,
        port_id,
        version,
        type_ids,
        last_seen,
        serial,
        mac,
        d_state={},
    ) -> None:
        _LOGGER.debug("Ryobi GDODevice __init__")
        super().__init__(username, password, api_key, u_id, d_id)

        self.username = username
        self.password = password
        self.api_key = api_key
        self.user_id = u_id

        self.type_ids = type_ids
        self.device_id = d_id
        self.name = name
        self.version = version
        self.description = description
        self.module_id = module_id
        self.port_id = port_id
        self.last_seen = last_seen
        self.last_update = None
        self.serial = None
        self.mac = None
        self.wifi_version = None

        self.unique_id = str(name + "_" + d_id)

        if d_state is not None:
            self.garage_state = d_state
        else:
            self.garage_state = {
                "vacationMode": {
                    "lastValue": None,
                    "value": None,
                    "vacation_state": None
                },
                "sensorFlag": {
                    "lastSet": None,
                    "lastValue": None,
                    "value": None,
                },
                "doorState": {
                    "state": None,
                    "lastSet": None,
                    "lastValue": None,
                    "value": None,
                    "enum": ["Closed", "Open", "Closing", "Opening", "Fault"],
                },
                "doorPercentOpen": None,
                "doorPosition": {
                    "lastSet": None,
                    "lastValue": None,
                    "value": None,
                },
                "garageLight": {
                    "lightState": {
                        "lastSet": None,
                        "lastValue": None,
                        "value": None,
                    },
                    "lightTimer": {
                        "lastSet": None,
                        "lastValue": None,
                        "value": None,
                    },
                }
            }

    async def watch_state(self):
        """
        State watcher from VacDevice
        """
        _LOGGER.debug(
            "GdoDevice: starting state watcher for= %s %s", self.name, self.device_id
        )

        try:
            await self.refresh_handler(self.device_id)
        except Exception as err:
            _LOGGER.exception("Error on watch_state starting refresh_handler: %s", err)

    # ==========================================================
    # Garage Door Entity
    # -> Properties

    @property
    def current_state(self):
        """Raw current_state variable"""
        if "doorState" in self.garage_state:
            self.garage_state["doorState"]["state"] = self.garage_state["doorState"]["enum"][self.garage_state["doorState"]["value"]]
            return self.garage_state["doorState"]["state"]

    @property
    def is_available(self):
        """Raw is_available variable"""
        if "is_available" in self.garage_state:
            return self.garage_state["is_available"] #TODO not properly implemented to check

    @property
    def current_cover_position(self):
        """Raw cover position variable"""
        if "doorPosition" in self.garage_state:
            return self.garage_state["doorPosition"]["value"]

    @property
    def is_opening(self):
        """Raw is_opening variable"""
        if self.garage_state["doorState"]["state"] == "Opening":
            return True

    @property
    def is_closing(self):
        """Raw is_closing variable"""
        if self.garage_state["doorState"]["state"] == "Closing":
            return True

    @property
    def is_closed(self):
        """Raw is_closed variable"""
        if self.garage_state["doorState"]["state"] == "Closed":
            return True

    @property
    def error_info(self):
        """Raw error_info variable"""
        if self.garage_state["doorState"]["state"] == "Fault":
            return "Door in faulty State."

    # ==========================================================
    # Garage Door Entity
    # -> Methods

    def prepare_command_payload(self, command, data=None):
        """ Prapre the payload for sending over websocket """
        return {'jsonrpc': '2.0',
                'method': 'gdoModuleCommand',
                'params':
                    {'msgType': 16,
                    'moduleType': 5, #5 or self.module_id
                    'portId': self.port_id, #7
                    'moduleMsg':
                        command,
                    'topic': self.device_id}
                }

    async def open_cover(self):
        """Open garage door"""
        await self.send_command(self.prepare_command_payload(WS_CMD_COVER_OPEN))

    async def close_cover(self):
        """Close garage door"""
        await self.send_command(self.prepare_command_payload(WS_CMD_COVER_CLOSE))

    async def set_cover_position(self):
        """Set garage door position(height)"""
        await self.send_command(self.prepare_command_payload(WS_CMD_SET_POS, 1))  # TODO
