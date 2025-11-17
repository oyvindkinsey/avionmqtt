#!/bin/bash

# This install script was tested on a clean Raspberry Pi OS Lite (64-bit),
# but should also work on standard ubuntu etc.

SERVICE_NAME="avionmqtt"
SERVICE_USER="avion_mqtt"

# Create directory for service
mkdir "/usr/local/lib/$SERVICE_NAME"
cd "/usr/local/lib/$SERVICE_NAME"

apt install -y python3-pip python3-venv bluetooth

# Create virtual environment for python
python3 -m venv .venv
.venv/bin/python -m pip install avionmqtt

# Create the user the service will run as
useradd -r -s /bin/false $SERVICE_USER

# Create the system service itself
cat <<EOF > "/etc/systemd/system/$SERVICE_NAME.service"
[Unit]
Description=avion mqtt bridge
After=bluetooth.service network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
ExecStart=/usr/local/lib/$SERVICE_NAME/.venv/bin/avionmqtt -s /usr/local/lib/$SERVICE_NAME/settings.yaml
Restart=always
RestartSec=1
User=$SERVICE_USER

[Install]
WantedBy=default.target
EOF
systemctl daemon-reload

# Set service to start on boot
systemctl enable $SERVICE_NAME

# Create the settings file and open it for editing
cat <<EOF > settings.yaml
avion:
  email: email@example.com
  password: password

mqtt:
  host: mqtt.local
  username: avion
  password: avion

devices:
  import: true
  exclude_in_group: true

groups:
  import: true

all:
  name: "Entire mesh"
EOF
nano settings.yaml

# And we're done!
echo "Service installed - starting $SERVICE_NAME now"
systemctl restart $SERVICE_NAME
journalctl --unit $SERVICE_NAME
