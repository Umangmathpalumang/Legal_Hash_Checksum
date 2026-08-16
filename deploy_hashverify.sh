#!/usr/bin/env bash
# Hash Verify — deploy script
# Serves the tool on port 8506 using FastAPI + uvicorn
# Run this ON THE VPS: bash deploy_hashverify.sh
set -euo pipefail

echo "==> Hash Verify — setup"

PROJECT_DIR="$HOME/hashverify"
mkdir -p "$PROJECT_DIR/templates"
cd "$PROJECT_DIR"

echo "==> Creating virtual environment"
python3 -m venv "$PROJECT_DIR/venv"
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip -q
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q

echo "==> Installing systemd service on port 8506"
sudo tee /etc/systemd/system/hashverify.service > /dev/null << UNITEOF
[Unit]
Description=Hash Verify — File Checksum Tool
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8506 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNITEOF

sudo systemctl daemon-reload
sudo systemctl enable --now hashverify.service

echo "==> Opening firewall for port 8506"
sudo ufw allow 8506/tcp || true
REJECT_LINE=$(sudo iptables -L INPUT -n --line-numbers | grep "REJECT" | head -1 | awk '{print $1}')
if [ -n "${REJECT_LINE:-}" ]; then
  sudo iptables -I INPUT "${REJECT_LINE}" -p tcp --dport 8506 -j ACCEPT
else
  sudo iptables -I INPUT -p tcp --dport 8506 -j ACCEPT
fi
sudo netfilter-persistent save 2>/dev/null || true

echo "==> Health check"
sleep 3
curl -sf http://localhost:8506/health && echo " — healthy"

PUBLIC_IP="$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR-VPS-IP')"

echo ""
echo "=================================================================="
echo " Hash Verify is live at:  http://${PUBLIC_IP}:8506"
echo ""
echo " Add OCI Security List ingress rule for port 8506."
echo "=================================================================="
