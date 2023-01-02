import logging
from typing import Any
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntityFeature,
    CoverEntity,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING
)

from .gdodevice import GdoDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STATE_MAPPING = {
    "Closed": STATE_CLOSED,
    "Open": STATE_OPEN,
    "Closing": STATE_CLOSING,
    "Opening": STATE_OPENING,
}


async def async_setup_platform(
    hass: HomeAssistant,
    config,
    async_add_entities: entity_platform.AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up the Ryobi garage door openers."""
    garage_devices = []
    device: GdoDevice
    for device in hass.data[DOMAIN]:
        garage_devices.append(RyobiGarageDoor(device))
        hass.loop.create_task(device.watch_state())

    _LOGGER.debug("Adding Ryobi Garage Door to Home Assistant: %s", garage_devices)
    async_add_entities(garage_devices, False)


class RyobiGarageDoor(CoverEntity):
    """
    Ryobi Garage Door Opener
    """

    def __init__(self, device: GdoDevice) -> None:
        """
        Initialize the Ryobi Garage Door Opener in HA
        """
        self.device = device
        self.device.subscribe(lambda gdodevice: self.schedule_update_ha_state(False))
        self._error = None

        self._attr_device_class = CoverDeviceClass.GARAGE
        _LOGGER.info("Ryobi Garage Door Opener initialized: %s", self.name)

    @property
    def should_poll(self) -> bool:
        """Async update should_poll set to False"""
        return False

    # ==========================================================
    # Garade Door Entity
    # -> Properties

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SET_POSITION
        return supported_features

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.name

    @property
    def available(self) -> bool:
        """Returns true if vacuum is online"""
        _LOGGER.debug("Garage Door: available=%s", self.device.is_available)
        return self.device.is_available

    @property
    def state(self):
        """Return the current state of the vacuum."""
        try:
            mapped_state = STATE_MAPPING[self.device.current_state]
            _LOGGER.debug("Ryobi Cover: Ryobi State (%s) mapped to HA State = %s ", self.device.current_state, mapped_state)
        except KeyError:
            if self.device.current_state == "Fault":
                _LOGGER.error("Roybi Cover: The Garage Door is in a 'FAULT' state. Someting is wrong!")
            else:
                _LOGGER.error("Roybi Cover: Found an unsupported state, current_state: %s", self.device.current_state)
            return None

        return mapped_state

    @property
    def current_cover_position(self):
        """ Return current position of Garage Door """
        if self.device.current_state == "Closed":
            return -1
        elif self.device.current_state == "Open":
            return 100

        return self.device.garage_state["doorPosition"]["value"]

    @property
    def unique_id(self):
        """ Return the device's unique id """
        return self.device.unique_id

    @property
    def is_opening(self):
        """ Return return true if is_opening """
        return self.device.is_opening

    @property
    def is_closing(self):
        """ Return return true if is_closing """
        return self.device.is_closing

    @property
    def is_closed(self):
        """ Return true if closed """
        return self.device.is_closed

    @property
    def error(self):
        """ Return the device error """
        _LOGGER.debug("Garage Door error: %s", self.device.error_info)
        return self.device.error_info

    @property
    def extra_state_attributes(self) -> dict:
        """Return the device-specific state attributes of this cover."""
        unixtime = int(self.device.garage_state["doorState"]["lastSet"]) / 1000.0 #divide by 1000 to go form ms to s
        extra_value = {
            "garage_state": self.device.current_state,
            "door_last_set": datetime.fromtimestamp(unixtime).strftime('%Y-%m-%d %H:%M:%S'),
            "door_last_value": self.device.garage_state["doorState"]["lastValue"],
            "vacation_mode": self.device.garage_state["vacationMode"]["vacation_state"],
            "sensor_flag": self.device.garage_state["sensorFlag"]["value"],
            "door_percent_open": self.device.garage_state["doorPercentOpen"],
            "garage_light_state": self.device.garage_state["garageLight"]["lightState"]["value"],
            "garage_light_timer": self.device.garage_state["garageLight"]["lightTimer"]["value"],
            "error_info": self.device.error_info,
        }

        return extra_value

    # ==========================================================
    # Garade Door Entity
    # -> Methods

    async def async_open_cover(self, **kwargs: Any) -> None:
        """ Open the garage door """
        _LOGGER.debug("Open garage door (%s)", self.name)
        await self.device.open_cover()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """ Close the garage door """
        _LOGGER.debug("Closing garage door (%s)", self.name)
        await self.device.close_cover()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """ Set the garage door to certain position"""
        _LOGGER.debug("Setting garage door to position (%s)", self.name)
        #await self.device.set_cover_position()

