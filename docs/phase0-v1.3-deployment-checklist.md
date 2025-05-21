# Phase 0 (v1.3) Deployment Checklist

## Pre-Deployment Verification

### Code Quality
- [ ] All pre-commit hooks passing
- [ ] Static analysis (ruff, bandit) checks passing
- [ ] Code formatting (black) applied
- [ ] CI pipeline passing

### Testing
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] All BDD tests passing
- [ ] Manual testing completed in staging environment
- [ ] Performance testing completed

### Documentation
- [ ] All features documented
- [ ] API documentation updated
- [ ] Deployment guide updated
- [ ] Workflow documentation completed
- [ ] Compliance documentation completed

## Database Migration

### Preparation
- [ ] Database backup completed
- [ ] Migration scripts reviewed
- [ ] Rollback scripts prepared

### Migration Execution
- [ ] Run `postgres_raw_html_storage.sql` migration
- [ ] Run `postgres_llm_logs.sql` migration
- [ ] Verify database schema changes
- [ ] Verify indexes created correctly

## Configuration Updates

### Environment Variables
- [ ] Set `DATA_RETENTION_DAYS=90`
- [ ] Set `BOUNCE_RATE_THRESHOLD=0.02`
- [ ] Set `BATCH_COMPLETION_DEADLINE_HOUR=5`
- [ ] Set `BATCH_COMPLETION_TIMEZONE="America/New_York"`
- [ ] Set `MONTHLY_BUDGET` value

### Configuration Files
- [ ] Update `health_check_config.yml` with new threshold value
- [ ] Verify all configuration files have correct values
- [ ] Ensure proper permissions on configuration files

## Deployment Steps

### 1. Preparation
- [ ] Create deployment branch
- [ ] Tag release version
- [ ] Notify team of deployment schedule
- [ ] Schedule maintenance window if needed

### 2. Deployment
- [ ] Deploy code changes
- [ ] Run database migrations
- [ ] Update configuration files
- [ ] Set environment variables
- [ ] Restart services

### 3. Verification
- [ ] Verify services started correctly
- [ ] Check logs for errors
- [ ] Run health checks
- [ ] Verify metrics are reporting correctly
- [ ] Test unsubscribe functionality
- [ ] Confirm HTML storage is working
- [ ] Verify LLM logging is working

### 4. Monitoring
- [ ] Set up Prometheus alerts for new metrics
- [ ] Configure Grafana dashboards
- [ ] Verify alert thresholds
- [ ] Test alert notifications

## Post-Deployment Tasks

### Verification
- [ ] Verify email deliverability
- [ ] Confirm CAN-SPAM compliance
- [ ] Check batch completion monitoring
- [ ] Verify cost metrics reporting
- [ ] Test failover threshold

### Documentation
- [ ] Update system documentation with deployed changes
- [ ] Document any issues encountered during deployment
- [ ] Update runbooks if necessary

### Training
- [ ] Schedule team training on new features
- [ ] Update user guides
- [ ] Create FAQ for common questions

## Rollback Plan

### Triggers
- [ ] Define criteria for rollback decision
- [ ] Establish communication protocol for rollback

### Rollback Steps
- [ ] Revert code changes
- [ ] Rollback database migrations
- [ ] Restore configuration files
- [ ] Reset environment variables
- [ ] Restart services

### Verification After Rollback
- [ ] Verify services started correctly
- [ ] Check logs for errors
- [ ] Confirm system functionality

## Sign-off

- [ ] Development team sign-off
- [ ] QA team sign-off
- [ ] Operations team sign-off
- [ ] Security team sign-off
- [ ] Management sign-off

## Notes

- Schedule deployment during low-traffic period
- Ensure database backups are completed before migration
- Have team members available during deployment for quick response
- Monitor system closely for 24 hours after deployment
- Prepare communication templates for potential issues
