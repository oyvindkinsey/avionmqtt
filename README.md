# avionmqtt

A python library to bridge between Avi-on based lights and Home Assistant using MQTT

## support
This should support any devices that uses Avi-on's technology, including Halo Home and GE branded BLE lights (both discontinued, but both supported by Avi-on's cloud infra and mobile apps).

# features
- creates lights for devices and groups in Home Assistant
  - supports creating meta lights such as for 'all', usefull for automation of color temperature
- supports changing brightness and color temperature
  - for:
    - individidual devices
    - groups
    - the entire mesh at once
  - color temperature can be set *without* turning on the light
- polls the whole network on startup to get the current state of each device
- updates Home Assistant whenever devices are updated externally

# how to use

```bash
# if bluepy fails to compile, try installing libglib2.0-dev first (apt-get install libglib2.0-dev)
pip install avionmqtt
avionmqtt -s settings.yaml --log=INFO
```
 ## service install script
 See [Running as a service.md](resources/Running%20as%20a%20service.md) for how to install this as a service using systemd.

## settings.yaml

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
    # If set, include only these pids when importing devices
    include:
      - abcde...
      - bcdef...
    # If set, exclude these pids when importing devices
    exclude:
      - abcde...
      - bcdef...
    # If set, automatically adds all devices part of a group to the exclude list
    exclude_in_group: true

groups:
    import: true
    include:
    exclude:

# Controls if a single device, or one per light is created. Defaults to false.
single_device: true

# If you need to add additional overrides to dimmable or color_temp capabilities, then you can do so here.
# If new products are discovered to work with this library, create an issue on github so that it can be added in.
capabilities_overrides:
  dimming:
    - 123
    - 234
  color_temp:
    - 123
```

# acknowledgements
This project would not have been possible without the original work done in https://github.com/nkaminski/csrmesh and https://github.com/nayaverdier/halohome
