# Anthrasite Lead-Factory Deployment Guide

This document provides detailed instructions for deploying the Anthrasite Lead-Factory pipeline to production environments.

## Deployment Options

The Lead-Factory pipeline can be deployed in two primary configurations:

1. **Standard Deployment**: Single-server deployment with local Ollama and nightly RSYNC backup
2. **High-Availability Deployment**: Primary + standby servers with automatic failover

## Prerequisites

- Hetzner Cloud account (for primary and standby servers)
- Supabase account (for database and storage)
- SendGrid account with shared warm IP pool
- Docker and Docker Compose
- All required API keys (see `.env.example`)

## Standard Deployment

### 1. Server Provisioning

Provision a Hetzner Cloud server with the following specifications:

- **CPU**: 4 vCPU (minimum)
- **RAM**: 16 GB (minimum)
- **Storage**: 100 GB SSD
- **OS**: Ubuntu 22.04 LTS
- **Location**: Choose a location close to your target market

```bash
# Using Hetzner CLI (hcloud)
hcloud server create --name leadfactory-primary \
  --type cx41 \
  --image ubuntu-22.04 \
  --ssh-key your-ssh-key \
  --location nbg1
```

### 2. Base System Setup

SSH into the server and set up the base system:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y docker.io docker-compose git sqlite3 python3-pip rsync cron

# Enable Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Add your user to the Docker group
sudo usermod -aG docker $USER
```

### 3. Clone Repository

```bash
# Create application directory
mkdir -p /leadfactory
cd /leadfactory

# Clone repository
git clone https://github.com/anthrasite/lead-factory.git .
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit environment variables
nano .env
```

Ensure the following variables are properly configured:
- All API keys
- Supabase connection details
- TIER level (1, 2, or 3)
- MOCKUP_ENABLED flag
- RSYNC backup configuration

### 5. Set Up Ollama

```bash
# Pull the Ollama Docker image
docker pull ollama/ollama

# Create a persistent volume for Ollama models
docker volume create ollama-models

# Run Ollama container
docker run -d --name ollama \
  -p 11434:11434 \
  -v ollama-models:/root/.ollama \
  ollama/ollama

# Pull the Llama-3 8B model
docker exec -it ollama ollama pull llama3:8b
```

### 6. Initialize Database

```bash
# Create database directory
mkdir -p /leadfactory/data

# Initialize database with schema
sqlite3 /leadfactory/data/leadfactory.db < /leadfactory/db/migrations/2025-05-19_init.sql

# Seed initial data
python3 -c "import sqlite3; conn = sqlite3.connect('/leadfactory/data/leadfactory.db'); c = conn.cursor(); c.execute('INSERT INTO zip_queue (zip, metro, done) VALUES (\"10002\", \"New York\", 0), (\"98908\", \"Yakima\", 0), (\"46032\", \"Carmel\", 0)'); conn.commit()"
```

### 7. Configure Cron Job

```bash
# Create log directory
sudo mkdir -p /var/log/leadfactory
sudo chown $USER:$USER /var/log/leadfactory

# Add cron job
(crontab -l 2>/dev/null; echo "0 23 * * * bash /leadfactory/bin/run_nightly.sh >> /var/log/leadfactory/leadfactory.log 2>&1") | crontab -
```

### 8. Set Up Prometheus Exporter

```bash
# Create Docker Compose file for Prometheus
cat > docker-compose.yml << EOF
version: '3'
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    restart: always
EOF

# Create Prometheus configuration
cat > prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'leadfactory'
    static_configs:
      - targets: ['localhost:9090']
EOF

# Start Prometheus
docker-compose up -d
```

### 9. Configure RSYNC Backup

Set up the standby VPS for RSYNC backup:

```bash
# On the standby VPS
mkdir -p /leadfactory-backup
```

On the primary server, configure SSH key-based authentication to the standby VPS:

```bash
# Generate SSH key if needed
ssh-keygen -t ed25519 -f ~/.ssh/leadfactory_backup_key

# Copy SSH key to standby VPS
ssh-copy-id -i ~/.ssh/leadfactory_backup_key user@standby-vps-ip
```

## High-Availability Deployment

For high-availability deployment, follow the standard deployment steps for both primary and standby servers, then configure automatic failover:

### 1. Configure Health Check on Standby

Create a health check script on the standby server:

```bash
cat > /leadfactory-backup/health_check.sh << 'EOF'
#!/bin/bash

PRIMARY_IP="primary-server-ip"
FAILURE_COUNT_FILE="/leadfactory-backup/failure_count"
THRESHOLD=2

# Initialize failure count if it doesn't exist
if [ ! -f "$FAILURE_COUNT_FILE" ]; then
  echo 0 > "$FAILURE_COUNT_FILE"
fi

# Check if primary is responding
if ping -c 3 $PRIMARY_IP > /dev/null 2>&1; then
  # Reset failure count
  echo 0 > "$FAILURE_COUNT_FILE"
  exit 0
else
  # Increment failure count
  CURRENT_COUNT=$(cat "$FAILURE_COUNT_FILE")
  NEW_COUNT=$((CURRENT_COUNT + 1))
  echo $NEW_COUNT > "$FAILURE_COUNT_FILE"

  # Check if threshold reached
  if [ $NEW_COUNT -ge $THRESHOLD ]; then
    # Start Docker stack
    cd /leadfactory-backup
    docker-compose up -d

    # Send alert
    echo "Primary server down. Standby activated at $(date)" | mail -s "ALERT: Lead-Factory Failover Activated" alerts@anthrasite.io
  fi
fi
EOF

chmod +x /leadfactory-backup/health_check.sh
```

### 2. Add Health Check Cron Job

```bash
# Add cron job to run health check every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * /leadfactory-backup/health_check.sh >> /var/log/leadfactory/health_check.log 2>&1") | crontab -
```

## Monitoring Setup

### 1. Configure Grafana Cloud

1. Sign up for Grafana Cloud
2. Create a new Prometheus data source
3. Import the provided dashboard from `etc/alerts.yml`

### 2. Set Up Alert Rules

Configure the following alert rules in Grafana Cloud:

- **Bounce Rate Alert**: Trigger when bounce rate > 4% for 2 hours
- **Spam Rate Alert**: Trigger when spam rate > 0.1% for 1 hour
- **Cost Per Lead Alert**: Trigger when cost_per_lead exceeds tier threshold for 1 hour
- **Batch Completion Alert**: Trigger when batch misses 05:00 EST completion time

## Scaling Considerations

### 1. GPU Burst Scaling

When `personalisation_queue > 2000`, the system will automatically provision a Hetzner GPU instance:

```bash
# This is handled automatically by the pipeline
# To manually trigger:
python bin/scale_gpu.py --queue-size 2000
```

### 2. SendGrid IP Pool Switching

When bounce rate exceeds 2%, the system will automatically switch to a dedicated IP pool:

```bash
# This is handled automatically by the pipeline
# To manually trigger:
python bin/switch_ip_pool.py --bounce-rate 2.5
```

## Troubleshooting

### Common Issues

1. **Pipeline Stage Failure**
   - Check logs in `/var/log/leadfactory/leadfactory.log`
   - Verify API keys and rate limits

2. **Database Connection Issues**
   - Check Supabase connection status
   - Verify environment variables

3. **Ollama Model Loading**
   - Ensure Llama-3 8B model is properly downloaded
   - Check Ollama container logs: `docker logs ollama`

4. **RSYNC Backup Failure**
   - Verify SSH key authentication
   - Check network connectivity to standby VPS

### Support Contacts

For urgent issues, contact:
- Technical Support: support@anthrasite.io
- On-Call Engineer: oncall@anthrasite.io
