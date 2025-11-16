# Running avionmqtt as a service

This is based on the guide from <https://github.com/torfsen/python-systemd-tutorial>.

---

[This install script](https://github.com/oyvindkinsey/avionmqtt/blob/main/resources/install.sh) was tested on a clean Raspberry Pi OS Lite (64-bit), but should also work on standard ubuntu etc.

> [!CAUTION]
> You're about to run a shell script from the internet as root - inspect it first!

```bash
sudo bash -c "$(wget -qLO - https://github.com/oyvindkinsey/avionmqtt/raw/main/resources/install.sh)"
 ```
