# Updating color temp using automation

avionmqtt supports updating color temp for the entire mesh, regardless of lights being on or off, and without changing the state of the lights. It is therefore trivial to integrate with eg a sunset/sunrise automation, to allow all lights to track the desired color temperature.

To do this, the simplest approach is to use an `mqtt.publish` action:

```yaml
action: mqtt.publish
data:
  evaluate_payload: false
  qos: "0"
  topic: hmd/light/avid/0/command
  payload: "{\"color_temp\":200}"
```

Home Assistant uses mireds as its internal unit, so this is also what avionmqtt expects. To convert from kelving to mireds, simply use `1000000 / $kelvin`, e.g `1000000/5000 = 200`.  Here 5000 kelvin = 200 mireds.
