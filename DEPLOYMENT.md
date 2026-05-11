# AWS EC2 Deployment Guide (Gunicorn Direct)

This guide will help you deploy the DZ Commodities Django application to AWS EC2 using Docker Compose with direct Gunicorn access (no Nginx).

## Prerequisites

1. AWS EC2 instance (Ubuntu 22.04 LTS recommended)
2. Domain name with DNS configured to point to EC2 public IP
3. SSL certificate (Let's Encrypt or AWS ACM)

## SSL/TLS Options

### Option 1: AWS Application Load Balancer (Recommended)
- Best for production
- Free SSL via AWS ACM
- Handles HTTP to HTTPS redirect
- Extra cost (~$16-20/month)

### Option 2: Direct EC2 with Let's Encrypt
- No extra AWS cost
- Requires manual setup
- Good for smaller deployments

---

## Deployment with AWS ALB (Recommended)

### 1. Create AWS ALB
- Go to AWS Console → EC2 → Load Balancers
- Create Application Load Balancer
- Add your domain to listeners (HTTP, HTTPS)
- Configure ACM certificate for HTTPS

### 2. Create Target Group
- Create target group for port 8000
- Register your EC2 instance

### 3. Deploy Application
```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repository
cd /opt
sudo git clone https://github.com/your-username/dz.git
cd dz
sudo chown -R ubuntu:ubuntu .

# Configure environment
cp .env.example .env
nano .env
```

Update `.env`:
```
DJANGO_ENV=production
DJANGO_SECRET_KEY=generate-strong-random-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
POSTGRES_PASSWORD=strong-postgres-password
EMAIL_HOST=smtp.mailgun.org
EMAIL_HOST_USER=your-mailgun-username
EMAIL_HOST_PASSWORD=your-mailgun-password
```

```bash
# Deploy
docker-compose up -d --build
docker-compose exec app python manage.py migrate
```

### 4. Configure ALB Health Check
- Path: `/`
- Protocol: HTTP
- Port: 8000
- Interval: 30s
- Timeout: 5s
- Healthy threshold: 3
- Unhealthy threshold: 3

---

## Deployment with Let's Encrypt (Direct EC2)

### 1. EC2 Instance Setup

```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for group changes to take effect
```

### 2. Clone and Configure

```bash
cd /opt
sudo git clone https://github.com/your-username/dz.git
cd dz
sudo chown -R ubuntu:ubuntu .

cp .env.example .env
nano .env
```

Update `.env`:
```
DJANGO_ENV=production
DJANGO_SECRET_KEY=generate-strong-random-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
POSTGRES_PASSWORD=strong-postgres-password
EMAIL_HOST=smtp.mailgun.org
EMAIL_HOST_USER=your-mailgun-username
EMAIL_HOST_PASSWORD=your-mailgun-password
```

### 3. Setup SSL with Caddy (Simpler than Certbot + Nginx)

```bash
# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy -y

# Create Caddyfile
sudo nano /etc/caddy/Caddyfile
```

Add to Caddyfile:
```
yourdomain.com {
    reverse_proxy localhost:8000
}

www.yourdomain.com {
    reverse_proxy localhost:8000
}
```

```bash
# Start Caddy
sudo systemctl enable caddy
sudo systemctl start caddy
```

### 4. Deploy Application

```bash
docker-compose up -d --build
docker-compose exec app python manage.py migrate
```

### 5. Configure AWS Security Group

Allow inbound traffic:
- HTTP (80) from 0.0.0.0/0
- HTTPS (443) from 0.0.0.0/0
- SSH (22) from your IP address only

---

## Maintenance Commands

```bash
# View logs
docker-compose logs -f app

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Start services
docker-compose up -d

# Update application
git pull
docker-compose up -d --build

# Backup database
docker-compose exec db pg_dump -U myuser mydatabase > backup.sql

# Restore database
docker-compose exec -T db psql -U myuser mydatabase < backup.sql

# Run migrations
docker-compose exec app python manage.py migrate

# Create superuser
docker-compose exec app python manage.py createsuperuser
```

## Troubleshooting

```bash
# Check container logs
docker-compose logs app
docker-compose logs db

# Restart specific service
docker-compose restart app

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Access Django shell
docker-compose exec app python manage.py shell

# Access PostgreSQL
docker-compose exec db psql -U myuser -d mydatabase
```

## Security Notes

1. Never commit `.env` files to version control
2. Use strong, unique passwords
3. Keep Docker and system packages updated
4. Regularly backup your database
5. Monitor logs for suspicious activity
6. Consider using AWS S3 for static/media files in production

## Performance Optimization

1. Enable Redis for caching (uncomment redis service in docker-compose.yml)
2. Use AWS S3 for static file storage in production
3. Consider using AWS RDS for PostgreSQL
4. Adjust Gunicorn workers based on EC2 instance size
   - 2-4 workers for t3.medium or similar
