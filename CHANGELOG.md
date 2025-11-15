# Changelog

## 1.0.0 2024-11-26
Initial commit

## 1.1.0 2024-11-26
Added basic shutdown handling

## 1.2.0 2024-11-26
Replaced dependency on halohome since it only provided limited support for API calls, which will need to be extended further.

## 1.2.3 2024-11-26
Added several small improvements, leaving the package in a reasonable usable state.

## 1.3.0 2024-12-01
- Create proper devices instead of dangling entities
- Add include and exclude options for registering devices
- Add option to automatically exclude devices part of a group

## 1.3.1 2024-12-09
- Add service install script

## 1.3.4 2024-12-09
- Remove use of retained messages and subcribe to Home Assistant's birth message instead

## 1.3.6 2024-12-09
- Add the product type to the name when the actual product name is unknown

## 1.3.7 2024-12-09
- add support for polling mesh via mqtt
- add support for using a single device in Home Assistant
- add support for overriding the device capabilities via the settings

## 1.3.8 2024-12-09
- add graceful handling of parsing errors

## 1.3.9 2024-12-14
- Use logger instead of print to avoid log spew. The log level is configurable via the command line.

## 1.3.10 2024-12-15
- add product name info and capabilities for Halo Home Light Adapter
- add product name info and capabilities for Halo Home Lamp Dimmer
- add product name info and capabilities for Halo Home Recessed Downlight (RL)

## 1.4.0 2025-05-19
- set the color temp range when creating entities
- gracefully handle mqtt deletes
- fix bug with missing kelvin to mireds conversion
- fix bug with automatic reconnect
- refactor code from functional to OOP

## 2.0.0  2025-11-14
- Large refactoring to allow mqtt and mesh to operate independently
