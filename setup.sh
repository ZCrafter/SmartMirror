#!/bin/bash
# setup.sh — Run once on the Pi to install everything
# Usage: bash setup.sh

set -e
MIRROR_DIR="$HOME/mirror"

echo "═══════════════════════════════════════"
echo "  Smart Mirror Setup"
echo "═══════════════════════════════════════"

# 1. System deps
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y nodejs npm python3-pip fswebcam python3-dotenv

# 2. Python deps
echo "[2/6] Installing Python packages..."
pip3 install requests python-dotenv RPi.GPIO --break-system-packages || \
pip3 install requests python-dotenv --break-system-packages

# 3. Node deps
echo "[3/6] Installing Node packages..."
cd "$MIRROR_DIR"
npm install

# 4. .env setup
if [ ! -f "$MIRROR_DIR/.env" ]; then
  cp "$MIRROR_DIR/.env.example" "$MIRROR_DIR/.env"
  echo ""
  echo "⚠️  Created .env — please fill in your credentials:"
  echo "    nano $MIRROR_DIR/.env"
fi

# 5. Systemd service — mirror server
echo "[4/6] Installing mirror server service..."
sudo tee /etc/systemd/system/mirror.service > /dev/null <<EOF
[Unit]
Description=Smart Mirror Node Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$MIRROR_DIR
ExecStart=/usr/bin/node $MIRROR_DIR/server/index.js
Restart=on-failure
RestartSec=5
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
EOF

# 6. Systemd service — button listener
echo "[5/6] Installing button listener service..."
sudo tee /etc/systemd/system/mirror-button.service > /dev/null <<EOF
[Unit]
Description=Smart Mirror Button Listener
After=mirror.service

[Service]
Type=simple
User=$USER
ExecStart=/usr/bin/python3 $MIRROR_DIR/scripts/button_listener.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 7. Autostart Chromium in kiosk mode
echo "[6/6] Setting up kiosk autostart..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/mirror.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Smart Mirror
Exec=bash -c 'sleep 5 && chromium-browser --kiosk --disable-infobars --noerrdialogs --disable-session-crashed-bubble --app=http://localhost:3000 --start-maximized --disable-restore-session-state'
EOF

sudo systemctl daemon-reload
sudo systemctl enable mirror.service mirror-button.service
sudo systemctl start mirror.service mirror-button.service

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit your credentials:  nano $MIRROR_DIR/.env"
echo "  2. Get Strava token:       node scripts/strava-auth.js"
echo "  3. Reboot to launch kiosk: sudo reboot"
echo "═══════════════════════════════════════"
