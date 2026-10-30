#!/usr/bin/env bash
# 1-Click Deployment Script for OmniLead 24/7 on Ubuntu/Debian Cloud VPS
set -e

echo "=========================================================="
echo "  Deploying OmniLead 24/7 Autonomous Agent on Cloud VPS"
echo "=========================================================="

APP_DIR="/opt/omnilead-agent"
sudo mkdir -p "$APP_DIR"
sudo cp -r ./* "$APP_DIR/"
cd "$APP_DIR"

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Create systemd service for 24/7 background execution & boot persistence
cat << 'EOF' | sudo tee /etc/systemd/system/omnilead.service
[Unit]
Description=OmniLead 24/7 Autonomous Sales Closer
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/omnilead-agent
ExecStart=/opt/omnilead-agent/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable omnilead
sudo systemctl restart omnilead

echo ""
echo "✅ OmniLead is now running 24/7 as a background service!"
echo "Status check: sudo systemctl status omnilead"
echo "Live logs: sudo journalctl -u omnilead -f"
echo "Access Dashboard at: http://YOUR_SERVER_IP:8000"
echo "=========================================================="
