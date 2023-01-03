
# Ryobi Garage Door Opener - HA Custom Component
Home Assistant custom component integration with Websocket-based connection to Ryobi's Cloud Service to control their Garage Door Opener. This was reverse-engineered from their Android App.

This integration will request all of the Garage Door devices linked to your Ryobi account and automatically add them into Home Assistant.

**This is a work-in-progress!** Currently, you can view the state (OPEN, CLOSED, OPENING, CLOSING) and the current position (% open) of the door. You can also open or close the door but **not set a position**. The Entity also has extra attributes such as Last Set, Last Value, Vacation Mode, Sensor Flag, Light State, and Light Timer. *The Light entity is not setup* and therefore not controllable yet.
### Tested Devices
- GDO125

## Setup
The Garage Door must first be setup and added through Ryobi's app. Once you've created an account and can successfully control the garage door from the app, you can use your login details with this integration. 
### Installation
Copy the `ryobi_garage` folder into your `config\custom_components\` folder. If `custom_components` doesn't exist then create it.
### Configuration.yaml 
    ryobi_garage:
      username: "username"
      password: "password"
### Restart HA
Once you've complete the above steps, restart Home Assistant. Once restarted, a new Garage Cover entity will be created using the name form the Ryobi App as the entity name.

## Project State and Contributing
Feel free to contribute to this project! I am not a professional programmer... just a dad who what to control his garage door from Home Assistant. Updates will be few and far-between.
### Issues
Please open an Issue and paste **DEBUG** logs or I can't help as easily. **PLEASE remove all personal login details, including your username, password, device IDs, and API Keys!!**

    logger:
      logs:
        custom_components.ryobi_garage: debug
        
### Functionality / To-Do 
See the [Projects board](https://github.com/users/CJOWood/projects/1) for updated list.
