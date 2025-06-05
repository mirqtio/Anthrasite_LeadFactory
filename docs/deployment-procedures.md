# LeadFactory Deployment Procedures

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Development Environment Setup](#development-environment-setup)
3. [Staging Deployment](#staging-deployment)
4. [Production Deployment](#production-deployment)
5. [Rollback Procedures](#rollback-procedures)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Emergency Procedures](#emergency-procedures)

## Pre-Deployment Checklist

### Code Review
- [ ] All code changes reviewed by at least 2 team members
- [ ] No unresolved comments in PR
- [ ] All CI checks passing
- [ ] Security scan completed (Bandit, safety)
- [ ] Performance impact assessed

### Testing
- [ ] Unit tests passing (coverage > 80%)
- [ ] Integration tests passing
- [ ] E2E tests passing
- [ ] Load tests performed for significant changes
- [ ] Manual testing completed on staging

### Documentation
- [ ] API documentation updated
- [ ] CHANGELOG.md updated
- [ ] Migration scripts documented
- [ ] Runbook updated with new procedures

### Dependencies
- [ ] All dependencies pinned to specific versions
- [ ] Security vulnerabilities checked
- [ ] License compliance verified
- [ ] Breaking changes in dependencies addressed

## Development Environment Setup

### Prerequisites

```bash
# System requirements
python --version  # 3.9+
node --version    # 14+
docker --version  # 20+
kubectl version   # 1.20+

# Required tools
pip install poetry
npm install -g yarn
brew install postgresql redis
```

### Local Setup

```bash
# Clone repository
git clone https://github.com/leadfactory/leadfactory.git
cd leadfactory

# Setup Python environment
poetry install
poetry shell

# Install pre-commit hooks
pre-commit install

# Setup environment variables
cp .env.example .env
# Edit .env with your configuration

# Start local services
docker-compose up -d postgres redis

# Run database migrations
alembic upgrade head

# Seed test data
python scripts/seed_database.py

# Start development server
python -m leadfactory.app
```

### Running Tests Locally

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=leadfactory --cov-report=html

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run with specific markers
pytest -m "not slow"
pytest -m "critical"
```

## Staging Deployment

### 1. Build and Push Docker Images

```bash
# Set version
export VERSION=$(git describe --tags --always)

# Build images
docker build -t leadfactory/api:$VERSION -f docker/api/Dockerfile .
docker build -t leadfactory/scraper:$VERSION -f docker/scraper/Dockerfile .
docker build -t leadfactory/enrichment:$VERSION -f docker/enrichment/Dockerfile .
docker build -t leadfactory/deduplication:$VERSION -f docker/deduplication/Dockerfile .
docker build -t leadfactory/scoring:$VERSION -f docker/scoring/Dockerfile .
docker build -t leadfactory/mockup:$VERSION -f docker/mockup/Dockerfile .
docker build -t leadfactory/email:$VERSION -f docker/email/Dockerfile .

# Push to registry
docker push leadfactory/api:$VERSION
docker push leadfactory/scraper:$VERSION
docker push leadfactory/enrichment:$VERSION
docker push leadfactory/deduplication:$VERSION
docker push leadfactory/scoring:$VERSION
docker push leadfactory/mockup:$VERSION
docker push leadfactory/email:$VERSION
```

### 2. Deploy to Staging Kubernetes

```bash
# Switch to staging context
kubectl config use-context staging

# Update image versions in manifests
export VERSION=$(git describe --tags --always)
envsubst < k8s/staging/deployment.yaml | kubectl apply -f -

# Apply configurations
kubectl apply -f k8s/staging/configmap.yaml
kubectl apply -f k8s/staging/secrets.yaml

# Run database migrations
kubectl run migration --rm -it --image=leadfactory/api:$VERSION \
  --restart=Never -- alembic upgrade head

# Verify deployment
kubectl rollout status deployment/api -n leadfactory
kubectl rollout status deployment/scraper -n leadfactory
kubectl rollout status deployment/enrichment -n leadfactory
```

### 3. Staging Validation

```bash
# Run smoke tests
python scripts/smoke_tests.py --env staging

# Run integration tests against staging
pytest tests/staging/ --env staging

# Check application logs
kubectl logs -f deployment/api -n leadfactory

# Monitor metrics
open https://staging-metrics.leadfactory.com
```

## Production Deployment

### 1. Pre-Production Steps

```bash
# Create deployment ticket
./scripts/create_deployment_ticket.sh

# Notify team
./scripts/notify_deployment.sh --env production --version $VERSION

# Backup database
./scripts/backup_postgres.sh --env production

# Check system health
./scripts/health_check.sh --env production
```

### 2. Blue-Green Deployment

```bash
# Deploy to green environment
kubectl config use-context production

# Scale up green deployment
kubectl apply -f k8s/production/deployment-green.yaml

# Wait for green to be ready
kubectl wait --for=condition=ready pod -l version=green -n leadfactory

# Run migrations on green
kubectl exec -it deployment/api-green -n leadfactory -- alembic upgrade head

# Switch traffic to green (10% canary)
kubectl apply -f k8s/production/canary-10.yaml

# Monitor metrics (wait 10 minutes)
./scripts/monitor_canary.sh --duration 10m

# If metrics good, increase to 50%
kubectl apply -f k8s/production/canary-50.yaml

# Monitor metrics (wait 10 minutes)
./scripts/monitor_canary.sh --duration 10m

# If metrics good, complete rollout
kubectl apply -f k8s/production/canary-100.yaml

# Scale down blue deployment
kubectl scale deployment api-blue --replicas=0 -n leadfactory
```

### 3. Database Migrations

```bash
# For backwards-compatible migrations
kubectl exec -it deployment/api-green -n leadfactory -- \
  alembic upgrade head

# For breaking changes (requires maintenance window)
# 1. Enable maintenance mode
kubectl apply -f k8s/production/maintenance.yaml

# 2. Stop workers
kubectl scale deployment scraper enrichment deduplication --replicas=0 -n leadfactory

# 3. Run migration
kubectl exec -it deployment/api-green -n leadfactory -- \
  alembic upgrade head

# 4. Start workers
kubectl scale deployment scraper enrichment deduplication --replicas=3 -n leadfactory

# 5. Disable maintenance mode
kubectl delete -f k8s/production/maintenance.yaml
```

## Rollback Procedures

### Immediate Rollback (< 5 minutes)

```bash
# Switch traffic back to blue
kubectl apply -f k8s/production/rollback-blue.yaml

# Scale down green
kubectl scale deployment api-green --replicas=0 -n leadfactory

# Notify team
./scripts/notify_rollback.sh --env production --reason "$REASON"
```

### Database Rollback

```bash
# Only if migration was applied
kubectl exec -it deployment/api-blue -n leadfactory -- \
  alembic downgrade -1

# Restore from backup if needed
./scripts/restore_postgres.sh --env production --backup $BACKUP_ID
```

### Full Environment Rollback

```bash
# Revert all services to previous version
export PREVIOUS_VERSION=$(git describe --tags --always HEAD~1)

# Update all deployments
kubectl set image deployment/api api=leadfactory/api:$PREVIOUS_VERSION -n leadfactory
kubectl set image deployment/scraper scraper=leadfactory/scraper:$PREVIOUS_VERSION -n leadfactory
kubectl set image deployment/enrichment enrichment=leadfactory/enrichment:$PREVIOUS_VERSION -n leadfactory
# ... repeat for all services

# Wait for rollout
kubectl rollout status deployment --all -n leadfactory
```

## Post-Deployment Verification

### Automated Checks

```bash
# Run post-deployment tests
python scripts/post_deployment_tests.py --env production

# Verify API endpoints
./scripts/verify_endpoints.sh --env production

# Check error rates
./scripts/check_error_rates.sh --threshold 0.01

# Verify background jobs
./scripts/verify_workers.sh
```

### Manual Verification

1. **API Health**
   ```bash
   curl https://api.leadfactory.com/health
   ```

2. **Critical User Flows**
   - Create new pipeline
   - Process test business
   - Send test email
   - Generate test report

3. **Monitoring Dashboards**
   - Check Grafana: https://metrics.leadfactory.com
   - Check error tracking: https://sentry.leadfactory.com
   - Check APM: https://newrelic.leadfactory.com

4. **Database Performance**
   ```sql
   -- Check slow queries
   SELECT query, calls, mean_time
   FROM pg_stat_statements
   WHERE mean_time > 1000
   ORDER BY mean_time DESC
   LIMIT 10;
   ```

## Emergency Procedures

### Service Degradation

```bash
# Enable circuit breakers
kubectl set env deployment/api CIRCUIT_BREAKER_ENABLED=true -n leadfactory

# Disable non-critical features
kubectl set env deployment/api FEATURES_ENRICHMENT=false -n leadfactory
kubectl set env deployment/api FEATURES_EMAIL=false -n leadfactory

# Scale up critical services
kubectl scale deployment api --replicas=10 -n leadfactory
kubectl scale deployment scraper --replicas=5 -n leadfactory
```

### Database Issues

```bash
# Switch to read replica
kubectl set env deployment/api DATABASE_URL=$READ_REPLICA_URL -n leadfactory

# Enable connection pooling limits
kubectl set env deployment/api DB_POOL_SIZE=5 -n leadfactory
kubectl set env deployment/api DB_MAX_OVERFLOW=10 -n leadfactory
```

### Complete Outage

```bash
# 1. Enable maintenance page
kubectl apply -f k8s/emergency/maintenance-page.yaml

# 2. Notify customers
./scripts/notify_customers.sh --template outage

# 3. Debug issues
kubectl get events -n leadfactory
kubectl describe pods -n leadfactory
kubectl logs -f deployment/api -n leadfactory --tail=100

# 4. If needed, restore from backup region
./scripts/failover_to_region.sh --region us-east-1
```

## Deployment Schedule

### Regular Deployments
- **Production**: Tuesdays and Thursdays, 2 PM PST
- **Staging**: Daily at 10 AM PST
- **Hotfixes**: As needed with approval

### Maintenance Windows
- **Scheduled**: First Sunday of month, 2-4 AM PST
- **Emergency**: As needed with 2-hour notice

### Deployment Freeze Periods
- Black Friday through Cyber Monday
- December 15 - January 2
- Major holidays

## Contact Information

### Deployment Team
- **Primary**: devops@leadfactory.com
- **Escalation**: cto@leadfactory.com
- **Emergency**: +1-555-DEPLOY-911

### Key Personnel
- **DevOps Lead**: John Doe (john@leadfactory.com)
- **Platform Engineer**: Jane Smith (jane@leadfactory.com)
- **SRE**: Bob Johnson (bob@leadfactory.com)

### External Contacts
- **AWS Support**: Premium support case
- **Datadog**: support@datadog.com
- **PagerDuty**: Automated escalation

## Appendix

### Useful Commands

```bash
# Get deployment history
kubectl rollout history deployment/api -n leadfactory

# Check resource usage
kubectl top nodes
kubectl top pods -n leadfactory

# Get recent events
kubectl get events -n leadfactory --sort-by='.lastTimestamp'

# Debug pod issues
kubectl describe pod <pod-name> -n leadfactory
kubectl logs <pod-name> -n leadfactory --previous

# Access pod shell
kubectl exec -it <pod-name> -n leadfactory -- /bin/bash

# Port forward for debugging
kubectl port-forward service/api 8080:80 -n leadfactory
```

### Configuration Files

All deployment configurations are stored in:
- `k8s/` - Kubernetes manifests
- `docker/` - Dockerfile definitions
- `scripts/` - Deployment scripts
- `.github/workflows/` - CI/CD pipelines

### Monitoring URLs

- Production Metrics: https://metrics.leadfactory.com
- Staging Metrics: https://staging-metrics.leadfactory.com
- Status Page: https://status.leadfactory.com
- Logs: https://logs.leadfactory.com
