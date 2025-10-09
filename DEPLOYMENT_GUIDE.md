# Laitusneo - Deployment Guide

## 🚀 Production Deployment Guide

This guide will walk you through deploying Laitusneo to a production environment.

## 📋 Prerequisites

### System Requirements
- **Operating System**: Ubuntu 20.04 LTS or CentOS 8+
- **Python**: 3.8 or higher
- **MySQL**: 5.7 or higher
- **Memory**: Minimum 2GB RAM (4GB recommended)
- **Storage**: Minimum 10GB free space
- **Network**: Stable internet connection

### Software Dependencies
- Python 3.8+
- MySQL Server
- Nginx (web server)
- Gunicorn (WSGI server)
- Git (version control)

## 🛠️ Installation Steps

### 1. Server Setup

#### Update System Packages
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

#### Install Required Packages
```bash
# Ubuntu/Debian
sudo apt install -y python3 python3-pip python3-venv mysql-server nginx git

# CentOS/RHEL
sudo yum install -y python3 python3-pip mysql-server nginx git
```

### 2. Database Setup

#### Install and Configure MySQL
```bash
# Start MySQL service
sudo systemctl start mysql
sudo systemctl enable mysql

# Secure MySQL installation
sudo mysql_secure_installation
```

#### Create Database and User
```sql
-- Login to MySQL
sudo mysql -u root -p

-- Create database
CREATE DATABASE expense_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user
CREATE USER 'laitusneo_user'@'localhost' IDENTIFIED BY 'secure_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON expense_tracker.* TO 'laitusneo_user'@'localhost';
FLUSH PRIVILEGES;

-- Exit MySQL
EXIT;
```

### 3. Application Deployment

#### Create Application Directory
```bash
sudo mkdir -p /var/www/laitusneo
sudo chown $USER:$USER /var/www/laitusneo
cd /var/www/laitusneo
```

#### Clone Repository
```bash
git clone <your-repository-url> .
```

#### Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Install Dependencies
```bash
pip install -r requirements.txt
```

#### Create Required Directories
```bash
mkdir -p uploads exports uploads/templates
chmod 755 uploads exports uploads/templates
```

### 4. Configuration

#### Environment Configuration
```bash
# Create environment file
nano .env
```

Add the following content:
```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=your-very-secure-secret-key-here

# Database Configuration
DB_HOST=localhost
DB_USER=laitusneo_user
DB_PASSWORD=secure_password_here
DB_NAME=expense_tracker

# File Upload Configuration
UPLOAD_FOLDER=/var/www/laitusneo/uploads
EXPORT_FOLDER=/var/www/laitusneo/exports
MAX_CONTENT_LENGTH=16777216

# Security Configuration
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
```

#### Update Application Configuration
```bash
# Edit app.py to use environment variables
nano app.py
```

Update the database configuration section:
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'expense_tracker')
}
```

### 5. Database Initialization

#### Run Database Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Run database initialization
python3 -c "from app import create_tables; create_tables()"
```

### 6. Gunicorn Configuration

#### Create Gunicorn Configuration File
```bash
nano gunicorn.conf.py
```

Add the following content:
```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
user = "www-data"
group = "www-data"
```

#### Create Systemd Service
```bash
sudo nano /etc/systemd/system/laitusneo.service
```

Add the following content:
```ini
[Unit]
Description=Laitusneo Gunicorn daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/laitusneo
Environment="PATH=/var/www/laitusneo/venv/bin"
ExecStart=/var/www/laitusneo/venv/bin/gunicorn --config gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Start and Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl start laitusneo
sudo systemctl enable laitusneo
sudo systemctl status laitusneo
```

### 7. Nginx Configuration

#### Create Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/laitusneo
```

Add the following content:
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # File upload size
    client_max_body_size 16M;

    # Static files
    location /static {
        alias /var/www/laitusneo/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Uploads and exports
    location /uploads {
        alias /var/www/laitusneo/uploads;
        expires 1d;
    }

    location /exports {
        alias /var/www/laitusneo/exports;
        expires 1d;
    }

    # Main application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Error pages
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
}
```

#### Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/laitusneo /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 8. SSL Certificate (Let's Encrypt)

#### Install Certbot
```bash
# Ubuntu/Debian
sudo apt install -y certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install -y certbot python3-certbot-nginx
```

#### Obtain SSL Certificate
```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

#### Auto-renewal
```bash
sudo crontab -e
```

Add the following line:
```bash
0 12 * * * /usr/bin/certbot renew --quiet
```

### 9. Firewall Configuration

#### Configure UFW (Ubuntu)
```bash
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

#### Configure Firewalld (CentOS)
```bash
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 🔧 Configuration Management

### Environment Variables

#### Production Environment
```bash
# Create production environment file
nano .env.production
```

```env
FLASK_ENV=production
DEBUG=False
SECRET_KEY=your-production-secret-key
DB_HOST=localhost
DB_USER=laitusneo_user
DB_PASSWORD=secure_production_password
DB_NAME=expense_tracker
```

#### Development Environment
```bash
# Create development environment file
nano .env.development
```

```env
FLASK_ENV=development
DEBUG=True
SECRET_KEY=your-development-secret-key
DB_HOST=localhost
DB_USER=laitusneo_user
DB_PASSWORD=secure_development_password
DB_NAME=expense_tracker_dev
```

### Application Settings

#### Production Settings
```python
# app.py
class ProductionConfig:
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
```

## 📊 Monitoring and Logging

### Application Logging

#### Configure Logging
```python
# app.py
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/laitusneo.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Laitusneo startup')
```

#### Log Rotation
```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/laitusneo
```

```bash
/var/www/laitusneo/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload laitusneo
    endscript
}
```

### System Monitoring

#### Install Monitoring Tools
```bash
# Install htop for system monitoring
sudo apt install -y htop

# Install MySQL monitoring
sudo apt install -y mytop
```

#### Create Monitoring Script
```bash
nano /var/www/laitusneo/monitor.sh
```

```bash
#!/bin/bash

# Check if services are running
systemctl is-active --quiet laitusneo || echo "Laitusneo service is down"
systemctl is-active --quiet nginx || echo "Nginx service is down"
systemctl is-active --quiet mysql || echo "MySQL service is down"

# Check disk space
df -h | awk '$5 > 80 {print $0}'

# Check memory usage
free -h | awk 'NR==2{printf "Memory Usage: %s/%s (%.2f%%)\n", $3,$2,$3*100/$2 }'

# Check database connections
mysql -u laitusneo_user -p -e "SHOW PROCESSLIST;" | wc -l
```

```bash
chmod +x /var/www/laitusneo/monitor.sh
```

## 🔄 Backup and Recovery

### Database Backup

#### Automated Backup Script
```bash
nano /var/www/laitusneo/backup_db.sh
```

```bash
#!/bin/bash

# Configuration
DB_NAME="expense_tracker"
DB_USER="laitusneo_user"
DB_PASS="secure_password_here"
BACKUP_DIR="/var/backups/laitusneo"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Create database backup
mysqldump -u $DB_USER -p$DB_PASS $DB_NAME > $BACKUP_DIR/db_backup_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/db_backup_$DATE.sql

# Remove backups older than 30 days
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +30 -delete

echo "Database backup completed: db_backup_$DATE.sql.gz"
```

#### File Backup Script
```bash
nano /var/www/laitusneo/backup_files.sh
```

```bash
#!/bin/bash

# Configuration
APP_DIR="/var/www/laitusneo"
BACKUP_DIR="/var/backups/laitusneo"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup uploads and exports
tar -czf $BACKUP_DIR/files_backup_$DATE.tar.gz -C $APP_DIR uploads exports

# Remove backups older than 30 days
find $BACKUP_DIR -name "files_backup_*.tar.gz" -mtime +30 -delete

echo "Files backup completed: files_backup_$DATE.tar.gz"
```

#### Schedule Backups
```bash
# Add to crontab
crontab -e
```

```bash
# Daily database backup at 2 AM
0 2 * * * /var/www/laitusneo/backup_db.sh

# Daily file backup at 3 AM
0 3 * * * /var/www/laitusneo/backup_files.sh

# Weekly full backup on Sunday at 1 AM
0 1 * * 0 /var/www/laitusneo/backup_full.sh
```

### Recovery Procedures

#### Database Recovery
```bash
# Stop application
sudo systemctl stop laitusneo

# Restore database
gunzip -c /var/backups/laitusneo/db_backup_YYYYMMDD_HHMMSS.sql.gz | mysql -u laitusneo_user -p expense_tracker

# Start application
sudo systemctl start laitusneo
```

#### File Recovery
```bash
# Stop application
sudo systemctl stop laitusneo

# Restore files
tar -xzf /var/backups/laitusneo/files_backup_YYYYMMDD_HHMMSS.tar.gz -C /var/www/laitusneo/

# Set permissions
sudo chown -R www-data:www-data /var/www/laitusneo/uploads /var/www/laitusneo/exports

# Start application
sudo systemctl start laitusneo
```

## 🚀 Performance Optimization

### Database Optimization

#### MySQL Configuration
```bash
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
```

```ini
[mysqld]
# Performance settings
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2
query_cache_size = 64M
query_cache_type = 1
max_connections = 200
```

#### Restart MySQL
```bash
sudo systemctl restart mysql
```

### Application Optimization

#### Gunicorn Optimization
```python
# gunicorn.conf.py
bind = "127.0.0.1:8000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
```

#### Nginx Optimization
```nginx
# /etc/nginx/nginx.conf
worker_processes auto;
worker_connections 1024;

# Gzip compression
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

# Caching
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## 🔒 Security Hardening

### System Security

#### Update System
```bash
sudo apt update && sudo apt upgrade -y
```

#### Configure Firewall
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

#### Disable Root Login
```bash
sudo nano /etc/ssh/sshd_config
```

```bash
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart ssh
```

### Application Security

#### Environment Security
```bash
# Secure environment file
chmod 600 .env
chown www-data:www-data .env
```

#### Database Security
```sql
-- Remove test databases
DROP DATABASE IF EXISTS test;

-- Remove anonymous users
DELETE FROM mysql.user WHERE User='';

-- Flush privileges
FLUSH PRIVILEGES;
```

## 📈 Scaling Considerations

### Horizontal Scaling

#### Load Balancer Configuration
```nginx
# /etc/nginx/sites-available/laitusneo
upstream laitusneo_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    location / {
        proxy_pass http://laitusneo_backend;
    }
}
```

#### Multiple Application Instances
```bash
# Create additional Gunicorn services
sudo cp /etc/systemd/system/laitusneo.service /etc/systemd/system/laitusneo-8001.service
sudo cp /etc/systemd/system/laitusneo.service /etc/systemd/system/laitusneo-8002.service

# Update port numbers in service files
sudo systemctl daemon-reload
sudo systemctl start laitusneo-8001
sudo systemctl start laitusneo-8002
```

### Database Scaling

#### Read Replicas
```sql
-- Configure master-slave replication
-- Master server configuration
[mysqld]
server-id = 1
log-bin = mysql-bin
binlog-format = ROW

-- Slave server configuration
[mysqld]
server-id = 2
relay-log = mysql-relay-bin
read-only = 1
```

## 🧪 Testing Deployment

### Health Checks

#### Application Health Check
```bash
curl -f http://localhost:8000/health || exit 1
```

#### Database Health Check
```bash
mysql -u laitusneo_user -p -e "SELECT 1" || exit 1
```

#### Nginx Health Check
```bash
curl -f http://localhost/ || exit 1
```

### Automated Testing

#### Create Test Script
```bash
nano /var/www/laitusneo/test_deployment.sh
```

```bash
#!/bin/bash

echo "Testing Laitusneo deployment..."

# Test database connection
mysql -u laitusneo_user -p -e "USE expense_tracker; SELECT COUNT(*) FROM users;" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Database connection: OK"
else
    echo "❌ Database connection: FAILED"
    exit 1
fi

# Test application response
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
if [ $HTTP_STATUS -eq 200 ]; then
    echo "✅ Application response: OK"
else
    echo "❌ Application response: FAILED (HTTP $HTTP_STATUS)"
    exit 1
fi

# Test static files
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/static/style.css)
if [ $HTTP_STATUS -eq 200 ]; then
    echo "✅ Static files: OK"
else
    echo "❌ Static files: FAILED (HTTP $HTTP_STATUS)"
    exit 1
fi

echo "🎉 All tests passed! Deployment is successful."
```

```bash
chmod +x /var/www/laitusneo/test_deployment.sh
```

## 📞 Support and Maintenance

### Regular Maintenance Tasks

#### Weekly Tasks
- [ ] Check system logs for errors
- [ ] Verify backup integrity
- [ ] Update system packages
- [ ] Monitor disk space usage
- [ ] Check application performance

#### Monthly Tasks
- [ ] Review security logs
- [ ] Update application dependencies
- [ ] Test disaster recovery procedures
- [ ] Review and optimize database
- [ ] Update SSL certificates

#### Quarterly Tasks
- [ ] Security audit
- [ ] Performance review
- [ ] Backup strategy review
- [ ] Disaster recovery testing
- [ ] Documentation updates

### Troubleshooting

#### Common Issues

1. **Application Won't Start**
   ```bash
   sudo systemctl status laitusneo
   sudo journalctl -u laitusneo -f
   ```

2. **Database Connection Issues**
   ```bash
   mysql -u laitusneo_user -p -e "SHOW PROCESSLIST;"
   ```

3. **Nginx Configuration Issues**
   ```bash
   sudo nginx -t
   sudo systemctl status nginx
   ```

4. **SSL Certificate Issues**
   ```bash
   sudo certbot certificates
   sudo certbot renew --dry-run
   ```

### Support Contacts

- **Technical Support**: [support-email]
- **Emergency Support**: [emergency-phone]
- **Documentation**: [documentation-url]
- **Community Forum**: [forum-url]

---

This deployment guide provides comprehensive instructions for deploying Laitusneo to a production environment. Follow these steps carefully and test thoroughly before going live.

*Last updated: [Current Date]*
