"""The Ryobi Garage Door Opener integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .gdodevice import GdoDevice
from .ryobiapi import RyobiApi

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_DEVICE_ID): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config) -> bool:
    """Set up the Ryobi component."""
    _LOGGER.info("Creating new Ryobi GDO component")

    hass.data[DOMAIN] = []

    ryobi_api = RyobiApi(
        config[DOMAIN].get(CONF_USERNAME), config[DOMAIN].get(CONF_PASSWORD)
    )

    _LOGGER.debug("RyobiApi login started")
    login_result = await ryobi_api.login()

    if not login_result:
        _LOGGER.error("Ryobi Garage component was unable to login. Failed to setup")
        return False

    devices = await ryobi_api.get_devices()
    if not devices:
        _LOGGER.error("Ryobi component was unable to find any devices. Failed to setup")
        return False

    for device in devices:
        _LOGGER.info(
            "Found device name: %s | Device Id: %s", device["name"], device["u_id"]
        )

        device_info = await ryobi_api.get_device(device["d_id"])

        garage_device = GdoDevice(
            config[DOMAIN].get(CONF_USERNAME),
            config[DOMAIN].get(CONF_PASSWORD),
            device["api_key"],
            device["u_id"],
            device["d_id"],
            device["name"],
            device["description"],
            device_info["module_id"],
            device_info["port_id"],
            device["version"],
            device["type_ids"],
            device["last_seen"],
            device_info["serial"],
            device_info["mac"],
            device_info["garage_state"]
        )
        hass.data[DOMAIN].append(garage_device)

    if hass.data[DOMAIN]:
        _LOGGER.debug("Starting Ryobi GDO components")
        hass.helpers.discovery.load_platform("cover", DOMAIN, {}, config)
    return True