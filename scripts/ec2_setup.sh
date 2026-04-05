#!/bin/bash
# EC2 setup script for Streamlit + Nginx
# Run this on a fresh Amazon Linux 2023 or Ubuntu EC2 instance

set -e

echo "Setting up NHTSA Recall Analyzer on EC2..."

# Update system
echo "Updating system packages..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$ID" == "amzn" ]]; then
        sudo yum update -y
        sudo yum install -y python3.11 python3.11-pip nginx git
    else
        sudo apt update && sudo apt upgrade -y
        sudo apt install -y python3.11 python3.11-venv nginx git
    fi
fi

# Create app directory
APP_DIR="/opt/nhtsa-analyzer"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Clone or copy your code
echo "Setting up application..."
cd $APP_DIR

# If this is a git repo, clone it
# git clone https://github.com/yourusername/nhtsa-recall-analyzer.git .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install frontend dependencies
pip install -r frontend/requirements.txt

# Create systemd service for Streamlit
echo "Creating systemd service..."
sudo tee /etc/systemd/system/streamlit.service > /dev/null <<EOF
[Unit]
Description=Streamlit NHTSA Analyzer
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR/frontend
Environment="PATH=$APP_DIR/venv/bin"
Environment="API_GATEWAY_URL=YOUR_API_GATEWAY_URL"
ExecStart=$APP_DIR/venv/bin/streamlit run app.py --server.port 8501 --server.headless true
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo "Configuring Nginx..."
sudo tee /etc/nginx/conf.d/streamlit.conf > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }

    location /_stcore/stream {
        proxy_pass http://localhost:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 86400;
    }
}
EOF

# Remove default nginx config if exists
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# Start services
echo "Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable streamlit
sudo systemctl start streamlit
sudo systemctl enable nginx
sudo systemctl restart nginx

# Show status
echo ""
echo "Setup complete!"
echo ""
echo "Services status:"
sudo systemctl status streamlit --no-pager || true
sudo systemctl status nginx --no-pager || true
echo ""
echo "The application should be accessible at:"
echo "  http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'YOUR_EC2_PUBLIC_IP'):80"
echo ""
echo "IMPORTANT: Update the API_GATEWAY_URL in /etc/systemd/system/streamlit.service"
echo "Then run: sudo systemctl daemon-reload && sudo systemctl restart streamlit"
