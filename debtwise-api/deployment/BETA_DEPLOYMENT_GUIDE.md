# DebtWise Beta Deployment Guide

This guide covers the deployment and maintenance of the DebtWise API in the beta environment.

## 📋 Prerequisites

1. **Server Requirements**
   - Ubuntu 20.04+ or similar Linux distribution
   - Docker 20.10+ and Docker Compose 1.29+
   - Minimum 4GB RAM, 2 CPU cores
   - 50GB storage
   - SSL certificates (managed by Traefik)

2. **Domain Configuration**
   - `beta-api.debtwise.com` → Beta API endpoint
   - `beta-monitoring.debtwise.com` → Grafana dashboard

3. **Required Secrets**
   - Database passwords
   - JWT secret keys
   - Redis password
   - Grafana admin password

## 🚀 Initial Deployment

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/your-org/debtwise.git
cd debtwise/debtwise-api/deployment/beta

# Copy and configure environment
cp .env.example .env
# Edit .env with your secure values
nano .env
```

### 2. Set Up Traefik (One-time setup)

```bash
# Create Docker network for Traefik
docker network create traefik-public

# Deploy Traefik (in separate directory)
docker run -d \
  --name traefik \
  --network traefik-public \
  -p 80:80 \
  -p 443:443 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ./traefik/acme.json:/acme.json \
  traefik:v2.10 \
  --providers.docker=true \
  --providers.docker.exposedbydefault=false \
  --entrypoints.web.address=:80 \
  --entrypoints.websecure.address=:443 \
  --certificatesresolvers.letsencrypt.acme.email=admin@debtwise.com \
  --certificatesresolvers.letsencrypt.acme.storage=/acme.json \
  --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
```

### 3. Deploy Beta Environment

```bash
# Run deployment script
./scripts/deploy.sh

# Or manually:
docker-compose -f docker-compose.beta.yml up -d
```

### 4. Verify Deployment

```bash
# Check service status
./scripts/deploy.sh status

# View logs
./scripts/deploy.sh logs api

# Test API health
curl https://beta-api.debtwise.com/api/v1/health
```

## 📊 Monitoring Setup

### 1. Access Grafana

1. Navigate to https://beta-monitoring.debtwise.com
2. Login with credentials from .env file
3. Import dashboards from `/monitoring/grafana/dashboards/`

### 2. Configure Alerts

```bash
# Edit Prometheus alerts
nano monitoring/prometheus/alerts.yml

# Restart Prometheus to apply
docker-compose -f docker-compose.beta.yml restart prometheus
```

### 3. View Metrics

- **API Metrics**: https://beta-api.debtwise.com/api/v1/monitoring/metrics
- **Health Status**: https://beta-api.debtwise.com/api/v1/monitoring/health/detailed
- **Error Logs**: https://beta-api.debtwise.com/api/v1/monitoring/errors

## 🔄 Update Deployment

### 1. Standard Update

```bash
# Pull latest changes
git pull origin main

# Update images and redeploy
./scripts/deploy.sh
```

### 2. Blue-Green Deployment

```bash
# Deploy new version alongside current
docker-compose -f docker-compose.beta.yml up -d --scale api=2

# Verify new version is healthy
curl https://beta-api.debtwise.com/api/v1/health

# Remove old containers
docker-compose -f docker-compose.beta.yml up -d --scale api=1 --no-recreate
```

### 3. Rollback

```bash
# Quick rollback to previous version
./scripts/deploy.sh rollback

# Or manually specify version
docker-compose -f docker-compose.beta.yml up -d \
  --set IMAGE_TAG=previous-tag
```

## 🛡️ Security Checklist

- [ ] All secrets are strong and unique
- [ ] Environment variables are properly set
- [ ] SSL certificates are valid and auto-renewing
- [ ] Database backups are configured and tested
- [ ] Rate limiting is enabled
- [ ] CORS origins are properly configured
- [ ] Monitoring alerts are set up
- [ ] Log rotation is configured

## 🔧 Maintenance Tasks

### Daily
- Monitor error rates and performance metrics
- Check disk space and memory usage
- Review security alerts

### Weekly
- Test backup restoration
- Review and rotate logs
- Update dependencies if needed
- Performance analysis

### Monthly
- Security audit
- Performance optimization
- Capacity planning
- Documentation updates

## 🚨 Troubleshooting

### API Not Responding

```bash
# Check container status
docker-compose -f docker-compose.beta.yml ps

# View recent logs
docker-compose -f docker-compose.beta.yml logs --tail=100 api

# Restart API service
docker-compose -f docker-compose.beta.yml restart api
```

### Database Issues

```bash
# Connect to database
docker-compose -f docker-compose.beta.yml exec db psql -U debtwise

# Check connections
SELECT count(*) FROM pg_stat_activity;

# Kill idle connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' AND state_change < now() - interval '1 hour';
```

### High Memory Usage

```bash
# Check memory usage by container
docker stats

# Restart specific service
docker-compose -f docker-compose.beta.yml restart redis

# Clear Redis cache if needed
docker-compose -f docker-compose.beta.yml exec redis redis-cli FLUSHDB
```

## 📞 Support Contacts

- **DevOps Team**: devops@debtwise.com
- **On-Call**: +1-xxx-xxx-xxxx
- **Slack Channel**: #debtwise-beta-ops

## 📚 Additional Resources

- [API Documentation](https://beta-api.debtwise.com/docs)
- [Monitoring Dashboard](https://beta-monitoring.debtwise.com)
- [Internal Wiki](https://wiki.debtwise.com/beta-deployment)