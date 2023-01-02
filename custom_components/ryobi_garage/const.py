"""Constants for the Ryobi Garage Door Opener integration."""

DOMAIN = "ryobi_garage"

#Websocket Commands
WS_CMD_COVER_OPEN = {"doorCommand": 1 }
WS_CMD_COVER_CLOSE = {"doorCommand": 0 }
WS_CMD_LIGHT_ON = {"lightState": True }
WS_CMD_LIGHT_OFF = {"lightState": False }
WS_CMD_SET_POS = ""