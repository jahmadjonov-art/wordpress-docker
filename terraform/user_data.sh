#!/bin/bash
set -e

# Install Docker
apt-get update -y
apt-get install -y ca-certificates curl gnupg git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

# Clone repo
git clone ${repo_url} /app
cd /app

# Write .env
cat > /app/finance/.env <<ENV
FINANCE_USER=${finance_user}
FINANCE_PASS=${finance_pass}
DATABASE_URL=sqlite:////data/finance.db
CRAIGSLIST_METROS=dallas,houston,atlanta,chicago,losangeles,memphis,oklahomacity,jacksonville,phoenix,nashville,kansascity,columbus,indianapolis,louisville,charlotte,birmingham,stockton,fresno,denver,saltlakecity,portland,seattle,minneapolis,stlouis,littlerock
SCRAPE_INTERVAL_HOURS=3
CA_OPERATION=${ca_operation}
TARGET_TRUCK=50000
TARGET_TRAILER=22000
TARGET_TAXES_PLATES=4500
TARGET_AUTHORITY=2200
TARGET_INSURANCE_DOWN=5000
TARGET_EQUIPMENT=3500
TARGET_OPERATING_RESERVE=18000
TARGET_CONTINGENCY=10500
ENV

# Start the app
docker compose up -d
