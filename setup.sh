#!/bin/bash
# setup.sh — Run once on the Pi to install everything
# Usage: bash setup.sh

set -e
MIRROR_DIR="$HOME/mirror"

echo "═══════════════════════════════════════"
echo "  Smart Mirror Setup"
echo "═══════════════════════════════════════"

# 1. System deps
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y nodejs npm python3-pip fswebcam v4l-utils python3-gpiod gpiod unclutter

# 2. Python deps
echo "[2/7] Installing Python packages..."
pip3 install requests python-dotenv --break-system-packages

# 3. Node deps
echo "[3/7] Installing Node packages..."
cd "$MIRROR_DIR"
npm install

# 4. .env setup
if [ ! -f "$MIRROR_DIR/.env" ]; then
  cp "$MIRROR_DIR/.env.example" "$MIRROR_DIR/.env"
  echo ""
  echo "⚠️  Created .env — please fill in your credentials:"
  echo "    nano $MIRROR_DIR/.env"
fi

# 5. Systemd service — mirror server (runs as root: needed for fswebcam + LED sysfs access)
echo "[4/7] Installing mirror server service..."
sudo tee /etc/systemd/system/mirror.service > /dev/null <<SERVICEEOF
[Unit]
Description=Smart Mirror Node Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$MIRROR_DIR
ExecStart=/usr/bin/node $MIRROR_DIR/server/index.js
Restart=on-failure
RestartSec=5
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
SERVICEEOF

# 6. Systemd service — button listener (gpiod-based, requires root for GPIO + LED)
echo "[5/7] Installing button listener service..."
sudo tee /etc/systemd/system/mirror-button.service > /dev/null <<SERVICEEOF
[Unit]
Description=Smart Mirror Button Listener
After=mirror.service

[Service]
Type=simple
User=root
WorkingDirectory=$MIRROR_DIR
ExecStart=/usr/bin/python3 $MIRROR_DIR/scripts/button_listener.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICEEOF

# 7. Systemd service — motion sensor daemon (HC-SR501 PIR)
echo "[6/7] Installing motion sensor service..."
sudo tee /etc/systemd/system/mirror-motion.service > /dev/null <<SERVICEEOF
[Unit]
Description=Smart Mirror Motion Sensor (HC-SR501)
After=mirror.service

[Service]
Type=simple
User=root
WorkingDirectory=$MIRROR_DIR
ExecStart=/usr/bin/python3 $MIRROR_DIR/scripts/motion_sensor.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICEEOF

# 8. Autostart Chromium in kiosk mode + hide cursor
echo "[7/7] Setting up kiosk autostart..."
mkdir -p "$HOME/.config/autostart"

cat > "$HOME/.config/autostart/mirror.desktop" <<DESKTOPEOF
[Desktop Entry]
Type=Application
Name=Smart Mirror
Exec=bash -c 'sleep 8 && pkill chromium; sleep 2 && chromium --kiosk --disable-infobars --noerrdialogs --disable-session-crashed-bubble --app=http://localhost:3000 --start-maximized --disable-restore-session-state --check-for-update-interval=31536000'
DESKTOPEOF

cat > "$HOME/.config/autostart/unclutter.desktop" <<DESKTOPEOF
[Desktop Entry]
Type=Application
Name=Hide Cursor
Exec=unclutter -idle 0.1 -root
DESKTOPEOF

# 9. udev rule so the LED sysfs paths are writable without per-boot chmod
echo "Setting up LED permissions rule..."
sudo tee /etc/udev/rules.d/99-led.rules > /dev/null <<'UDEVEOF'
SUBSYSTEM=="leds", ACTION=="add", RUN+="/bin/chmod a+w /sys%p/brightness /sys%p/trigger"
UDEVEOF

sudo systemctl daemon-reload
sudo systemctl enable mirror.service mirror-button.service mirror-motion.service
sudo systemctl start mirror.service mirror-button.service mirror-motion.service

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit your credentials:  nano $MIRROR_DIR/.env"
echo "     - Strava client ID/secret/refresh token"
echo "     - Immich URL/API key/album ID"
echo "     - WLED_URL (your ESP32's IP address)"
echo "     - MOTION_GPIO_PIN / MOTION_GRACE_SECONDS if you want non-defaults"
echo "  2. Get Strava token:       node scripts/strava-auth.js"
echo "  3. Wire HC-SR501: VCC->5V, GND->GND, OUT->GPIO17 (physical pin 11)"
echo "  4. Reboot to launch kiosk: sudo reboot"
echo "═══════════════════════════════════════"
