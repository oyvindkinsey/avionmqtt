# avionmqtt

A python library to control bridge between Avi-on based lights and Home Assistant using MQTT

## support
This should support any devices that uses Avi-on's technology, including Halo Home and GE branded BLE lights (both discontinued, but both supported by Avi-on's cloud infra and mobile apps).

# features
- creates lights for devices and groups in Home Assistant
- supports changing brightness and color temperature
- polls the whole network on startup to get the current state of each device
- updates Home Assistant whenever devices are updated externally 

# how to use

```bash
pip install avionmqtt
python -m avionmqtt -s settings.yaml
```

# settings.yaml

```yaml
avion:
    email: email@example.com
    password: ********

mqtt:
    host: mqtt_broker.local
    username: avion
    password: avion

devices:
    import: true

groups:
    import: true

```


# acknowledgements
This project would not have been possible without the original work done in https://github.com/nkaminski/csrmesh and https://github.com/nayaverdier/halohome