# Environment Variables and Alert Rules

This document provides a comprehensive overview of the environment variables and alert rules used in the Anthrasite LeadFactory project.

## Environment Variables

### Email Deliverability Configuration

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `BOUNCE_RATE_THRESHOLD` | Maximum acceptable bounce rate before blocking email sends | 0.02 (2%) |
| `SPAM_RATE_THRESHOLD` | Maximum acceptable spam complaint rate before blocking email sends | 0.001 (0.1%) |
| `SENDGRID_IP_POOL_NAMES` | Comma-separated list of SendGrid IP pool names to use for email sending | - |
| `SENDGRID_SUBUSER_NAMES` | Comma-separated list of SendGrid subuser names to use for email sending | - |
| `MONTHLY_BUDGET` | Monthly budget in dollars | 250 |

### Alert Thresholds

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `ALERT_BOUNCE_WARNING` | Warning threshold for email bounce rate | 0.01 (1%) |
| `ALERT_BOUNCE_CRITICAL` | Critical threshold for email bounce rate | 0.02 (2%) |
| `ALERT_SPAM_WARNING` | Warning threshold for email spam complaint rate | 0.0005 (0.05%) |
| `ALERT_SPAM_CRITICAL` | Critical threshold for email spam complaint rate | 0.001 (0.1%) |
| `ALERT_COST_TIER1_THRESHOLD` | Cost per lead threshold for Tier 1 | 3.0 dollars |
| `ALERT_COST_TIER2_THRESHOLD` | Cost per lead threshold for Tier 2 | 6.0 dollars |
| `ALERT_COST_TIER3_THRESHOLD` | Cost per lead threshold for Tier 3 | 10.0 dollars |
| `ALERT_GPU_BURST_THRESHOLD` | GPU burst cost threshold | 25.0 dollars |

## Alert Rules

The following alert rules are configured in Prometheus/Grafana for monitoring email deliverability metrics:

### Bounce Rate Alerts

#### BounceRateWarning
- **Condition**: `leadfactory_email_bounce_rate > 0.01` (1%)
- **Duration**: 15 minutes
- **Severity**: Warning
- **Description**: Triggered when the email bounce rate exceeds 1% for 15 minutes

#### BounceRateCritical
- **Condition**: `leadfactory_email_bounce_rate > 0.02` (2%)
- **Duration**: 5 minutes
- **Severity**: Critical
- **Description**: Triggered when the email bounce rate exceeds 2% for 5 minutes. At this level, email sending is automatically blocked.

### Spam Complaint Rate Alerts

#### SpamRateWarning
- **Condition**: `leadfactory_email_spam_rate > 0.0005` (0.05%)
- **Duration**: 15 minutes
- **Severity**: Warning
- **Description**: Triggered when the email spam complaint rate exceeds 0.05% for 15 minutes

#### SpamRateCritical
- **Condition**: `leadfactory_email_spam_rate > 0.001` (0.1%)
- **Duration**: 5 minutes
- **Severity**: Critical
- **Description**: Triggered when the email spam complaint rate exceeds 0.1% for 5 minutes. At this level, email sending is automatically blocked.

## Response Actions

When alerts are triggered, the following actions should be taken:

### Warning Level Alerts
1. Investigate the cause of the increased bounce or spam rates
2. Check the quality of the email list
3. Review email content for potential spam triggers
4. Consider adjusting email sending frequency or volume

### Critical Level Alerts
1. Immediately investigate the cause of the critical bounce or spam rates
2. Pause all email campaigns until the issue is resolved
3. Clean the email list to remove invalid or problematic addresses
4. Review and modify email content and templates
5. Contact SendGrid support if necessary

## CI Pipeline Configuration

The CI pipeline is configured to use these environment variables for testing. The variables are set in the GitHub Actions workflow files and are used to validate the email deliverability hardening features during the CI process.

To ensure consistent testing, the CI pipeline uses the same threshold values as the production environment:
- `BOUNCE_RATE_THRESHOLD=0.02`
- `SPAM_RATE_THRESHOLD=0.001`

## Monitoring Dashboard

A Grafana dashboard is available for monitoring email deliverability metrics in real-time. The dashboard displays:
- Current bounce rate
- Current spam complaint rate
- Historical trends for both metrics
- Alert status and history

Access the dashboard at: `https://grafana.anthrasite.com/dashboards/email-deliverability`
