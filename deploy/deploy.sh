#!/usr/bin/env bash
#
# deploy.sh — Full EC2 bootstrap for jobber-crawler
#
# Usage:
#   scp -i <key>.pem deploy.sh ubuntu@<ec2-ip>:~/deploy.sh
#   ssh -i <key>.pem ubuntu@<ec2-ip> "chmod +x ~/deploy.sh && ~/deploy.sh"
#
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
APP_DIR="$HOME/jobber-crawler"
REPO_URL="${JOBBER_REPO_URL:-git@github.com:your-org/jobber-crawler.git}"
DB_NAME="jobber_crawler"
DB_USER="jobber"
DB_PASS="${JOBBER_DB_PASSWORD:-$(openssl rand -base64 24)}"
PYTHON_VERSION="3.12"

# ─── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ─── Step 1: System packages ────────────────────────────────────────────────
info "Updating system packages..."
sudo apt update -qq && sudo apt upgrade -y -qq

info "Installing dependencies..."
sudo apt install -y -qq \
    python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python3-pip \
    postgresql postgresql-contrib \
    git curl build-essential \
    libxml2-dev libxslt-dev \
    nginx certbot python3-certbot-nginx

# ─── Step 2: PostgreSQL setup ───────────────────────────────────────────────
info "Configuring PostgreSQL..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create user and database (idempotent)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"

info "PostgreSQL ready — user: ${DB_USER}, db: ${DB_NAME}"

# ─── Step 3: Clone / update repo ────────────────────────────────────────────
if [ -d "$APP_DIR" ]; then
    info "Pulling latest changes..."
    cd "$APP_DIR" && git pull
else
    info "Cloning repository..."
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# ─── Step 4: Python venv & install ──────────────────────────────────────────
info "Setting up Python virtual environment..."
python${PYTHON_VERSION} -m venv .venv
source .venv/bin/activate

pip install --upgrade pip -q
pip install -e ".[dev]" -q
info "Python dependencies installed."

# ─── Step 5: Environment file ───────────────────────────────────────────────
if [ ! -f .env ]; then
    info "Creating .env file..."
    cat > .env << ENVEOF
# Database
JOBBER_DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}

# LinkedIn (uses free guest API — no API key needed)
JOBBER_LINKEDIN_ENABLED=true
JOBBER_LINKEDIN_RATE_LIMIT_RPM=20
JOBBER_LINKEDIN_MAX_RESULTS=1000
JOBBER_LINKEDIN_DELAY_SECONDS=3.0

# Naukri
JOBBER_NAUKRI_ENABLED=true
JOBBER_NAUKRI_RATE_LIMIT_RPM=30
JOBBER_NAUKRI_MAX_RESULTS=1000

# Indeed (disabled — aggressive bot detection)
JOBBER_INDEED_ENABLED=false
JOBBER_INDEED_PUBLISHER_ID=
JOBBER_INDEED_RATE_LIMIT_RPM=30
JOBBER_INDEED_MAX_RESULTS=1000

# Workday (comma-separated tenant URLs)
JOBBER_WORKDAY_ENABLED=true
JOBBER_WORKDAY_TENANT_URLS=
JOBBER_WORKDAY_RATE_LIMIT_RPM=60
JOBBER_WORKDAY_MAX_RESULTS=500

# Greenhouse (comma-separated board tokens)
JOBBER_GREENHOUSE_ENABLED=true
JOBBER_GREENHOUSE_BOARD_TOKENS=
JOBBER_GREENHOUSE_RATE_LIMIT_RPM=60
JOBBER_GREENHOUSE_MAX_RESULTS=500

# General
JOBBER_SCRAPE_CONCURRENCY=3
JOBBER_LOG_LEVEL=INFO
JOBBER_LOG_JSON=true
ENVEOF
    warn "Created .env — edit it to add Workday tenant URLs, Greenhouse tokens, etc."
else
    info ".env already exists, skipping."
fi

# ─── Step 6: Run migrations ─────────────────────────────────────────────────
info "Running database migrations..."
alembic upgrade head
info "Migrations complete."

# ─── Step 7: Systemd service ────────────────────────────────────────────────
info "Installing systemd service..."
sudo tee /etc/systemd/system/jobber-crawler.service > /dev/null << SVCEOF
[Unit]
Description=Jobber Crawler — Multi-source Job Scraper
After=postgresql.service network.target
Wants=postgresql.service

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn jobber_crawler.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jobber-crawler

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${APP_DIR}

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable jobber-crawler
sudo systemctl start jobber-crawler
info "Crawler service started."

# ─── Step 8: Nginx reverse proxy ────────────────────────────────────────────
info "Configuring Nginx reverse proxy..."
sudo tee /etc/nginx/sites-available/jobber-crawler > /dev/null << 'NGXEOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
NGXEOF

sudo ln -sf /etc/nginx/sites-available/jobber-crawler /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
info "Nginx configured."

# ─── Step 9: Print summary ──────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Deployment complete!"
echo ""
echo "  App directory:  ${APP_DIR}"
echo "  Database:       ${DB_NAME} (user: ${DB_USER})"
echo "  DB password:    ${DB_PASS}"
echo "  API:            http://$(curl -s ifconfig.me):80"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status jobber-crawler"
echo "    sudo journalctl -u jobber-crawler -f"
echo "    sudo systemctl restart jobber-crawler"
echo ""
echo "  Next: Run deploy/setup-claude-code.sh to install Claude Code"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
warn "SAVE YOUR DB PASSWORD: ${DB_PASS}"
echo ""
