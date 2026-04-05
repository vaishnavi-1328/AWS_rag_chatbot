#!/bin/bash
# Full EC2 setup script - Run this ON the EC2 instance
# Usage: bash ec2_full_setup.sh

set -e

echo "=========================================="
echo "NHTSA Recall Analyzer - EC2 Setup"
echo "=========================================="

# Check if running on EC2
if [[ ! -d "/opt/nhtsa-app" ]]; then
    echo "ERROR: /opt/nhtsa-app not found!"
    echo "Make sure you copied the project files first."
    exit 1
fi

# Step 1: Install system packages
echo ""
echo "[1/6] Installing system packages..."
sudo yum update -y
sudo yum install -y python3.11 python3.11-pip nginx

# Step 2: Install Python dependencies
echo ""
echo "[2/6] Installing Python dependencies..."
cd /opt/nhtsa-app
pip3.11 install --user streamlit boto3 requests python-dotenv

# Step 3: Create systemd service for Streamlit
echo ""
echo "[3/6] Creating Streamlit service..."
sudo tee /etc/systemd/system/streamlit.service > /dev/null << 'EOF'
[Unit]
Description=Streamlit NHTSA App
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/opt/nhtsa-app/frontend
Environment="PATH=/home/ec2-user/.local/bin:/usr/bin"
Environment="API_GATEWAY_URL=https://YOUR_API_GATEWAY_URL/prod"
ExecStart=/home/ec2-user/.local/bin/streamlit run app.py --server.port 8501 --server.headless true
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Step 4: Configure Nginx
echo ""
echo "[4/6] Configuring Nginx..."
sudo tee /etc/nginx/conf.d/streamlit.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
EOF

# Remove default nginx config if it exists
sudo rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true

# Step 5: Start services
echo ""
echo "[5/6] Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable streamlit
sudo systemctl enable nginx
sudo systemctl start nginx

# Step 6: Start Streamlit
echo ""
echo "[6/6] Starting Streamlit..."
sudo systemctl start streamlit

# Get public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "YOUR_EC2_PUBLIC_IP")

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "App URL: http://$PUBLIC_IP"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo "1. Update API Gateway URL in the service file:"
echo "   sudo nano /etc/systemd/system/streamlit.service"
echo "   (Change YOUR_API_GATEWAY_URL to your actual API Gateway URL)"
echo ""
echo "2. Then restart the service:"
echo "   sudo systemctl daemon-reload && sudo systemctl restart streamlit"
echo ""
echo "Check status with:"
echo "   sudo systemctl status streamlit"
echo "   sudo systemctl status nginx"
echo ""
