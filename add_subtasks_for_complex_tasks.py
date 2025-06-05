#!/usr/bin/env python3
import json
from datetime import datetime


def add_subtasks_for_complex_tasks():
    # Read the current tasks.json
    with open(".taskmaster/tasks/tasks.json") as f:
        data = json.load(f)

    # Find the tasks that need subtasks
    tasks_to_update = []

    for task in data["tasks"]:
        if task["id"] == 51:  # Bounce tracking + IP pool warm-up automation
            task["subtasks"] = [
                {
                    "id": 1,
                    "title": "Implement SendGrid webhook integration for bounce tracking",
                    "description": "Set up webhook endpoint to receive and process bounce notifications from SendGrid",
                    "dependencies": [],
                    "details": "Create secure webhook endpoint for SendGrid bounce events. Implement signature verification for security. Parse bounce types (hard/soft). Store bounce data in database. Add retry logic for webhook processing failures.",
                    "status": "pending",
                },
                {
                    "id": 2,
                    "title": "Design and implement IP warm-up schedule",
                    "description": "Create configurable warm-up schedule for new IP addresses",
                    "dependencies": [],
                    "details": "Design 30-day warm-up schedule with gradual volume increase. Create configuration for daily send limits. Implement schedule progression logic. Add support for multiple IPs. Include emergency pause functionality.",
                    "status": "pending",
                },
                {
                    "id": 3,
                    "title": "Build automated throttling system",
                    "description": "Implement send rate throttling based on warm-up schedule and reputation",
                    "dependencies": [1, 2],
                    "details": "Create throttling engine that respects warm-up limits. Implement rate limiting throughout the day. Add queue management for delayed sends. Monitor sending velocity. Include override capabilities for emergencies.",
                    "status": "pending",
                },
                {
                    "id": 4,
                    "title": "Create reputation monitoring and alerting",
                    "description": "Implement IP reputation tracking with automated alerts",
                    "dependencies": [1],
                    "details": "Monitor bounce rates, spam complaints, and engagement metrics. Track IP reputation scores. Create alerting thresholds. Implement automatic pausing for reputation issues. Add dashboard for reputation metrics.",
                    "status": "pending",
                },
                {
                    "id": 5,
                    "title": "Integration testing and deployment",
                    "description": "Complete testing and production deployment",
                    "dependencies": [1, 2, 3, 4],
                    "details": "Create comprehensive test suite for all components. Test webhook processing and data accuracy. Verify warm-up schedule enforcement. Test alerting and monitoring. Deploy to production with monitoring.",
                    "status": "pending",
                },
            ]
            tasks_to_update.append(task)

        elif task["id"] == 56:  # Add per-service daily spend caps
            task["subtasks"] = [
                {
                    "id": 1,
                    "title": "Implement cost tracking for each external service",
                    "description": "Create real-time cost tracking system for all API services",
                    "dependencies": [],
                    "details": "Track costs for OpenAI, SendGrid, Google APIs, Yelp API, etc. Implement cost calculation based on usage. Store cost data with service attribution. Create cost aggregation by service and time period.",
                    "status": "pending",
                },
                {
                    "id": 2,
                    "title": "Build configurable spend cap system",
                    "description": "Create configuration system for daily spending limits per service",
                    "dependencies": [],
                    "details": "Design YAML/JSON configuration for spend caps. Support per-service and global caps. Allow time-based caps (daily, weekly, monthly). Include cap adjustment APIs. Add validation for cap values.",
                    "status": "pending",
                },
                {
                    "id": 3,
                    "title": "Implement real-time cap enforcement",
                    "description": "Build system to enforce caps in real-time during API calls",
                    "dependencies": [1, 2],
                    "details": "Create middleware to check caps before API calls. Implement soft and hard cap limits. Add queuing for requests near caps. Include cap bypass for critical operations. Log all cap enforcement actions.",
                    "status": "pending",
                },
                {
                    "id": 4,
                    "title": "Create alerting and monitoring dashboard",
                    "description": "Build comprehensive monitoring for spend tracking and alerts",
                    "dependencies": [1, 3],
                    "details": "Create alerts for 80%, 90%, and 100% of caps. Build dashboard showing current spend vs caps. Add spend velocity tracking. Implement predictive alerts for cap breaches. Include historical spend analysis.",
                    "status": "pending",
                },
                {
                    "id": 5,
                    "title": "Testing and production rollout",
                    "description": "Comprehensive testing and gradual production deployment",
                    "dependencies": [1, 2, 3, 4],
                    "details": "Test cap enforcement accuracy. Verify no service disruption from caps. Test alerting at all thresholds. Implement gradual rollout with monitoring. Document cap configuration for operations team.",
                    "status": "pending",
                },
            ]
            tasks_to_update.append(task)

        elif task["id"] == 46:  # DB nightly backup + off-site sync
            task["subtasks"] = [
                {
                    "id": 1,
                    "title": "Set up automated backup infrastructure",
                    "description": "Configure database backup automation with scheduling",
                    "dependencies": [],
                    "details": "Set up cron jobs for nightly backups. Configure backup retention policies. Implement incremental backup strategy. Add backup compression. Create backup metadata tracking.",
                    "status": "pending",
                },
                {
                    "id": 2,
                    "title": "Implement off-site storage integration",
                    "description": "Set up secure off-site backup storage (S3/GCS)",
                    "dependencies": [],
                    "details": "Configure S3 or Google Cloud Storage bucket. Set up secure authentication. Implement encrypted transfer. Configure storage lifecycle policies. Add geographic redundancy.",
                    "status": "pending",
                },
                {
                    "id": 3,
                    "title": "Create backup verification system",
                    "description": "Implement automated backup integrity verification",
                    "dependencies": [1, 2],
                    "details": "Add checksum verification for backups. Implement test restore procedures. Create backup completeness checks. Add corruption detection. Schedule periodic restore tests.",
                    "status": "pending",
                },
                {
                    "id": 4,
                    "title": "Build monitoring and alerting",
                    "description": "Create comprehensive backup monitoring system",
                    "dependencies": [1, 2, 3],
                    "details": "Monitor backup job success/failure. Alert on backup failures. Track backup sizes and duration. Monitor storage usage and costs. Create backup status dashboard.",
                    "status": "pending",
                },
                {
                    "id": 5,
                    "title": "Documentation and disaster recovery procedures",
                    "description": "Create comprehensive documentation and DR procedures",
                    "dependencies": [1, 2, 3],
                    "details": "Document backup procedures. Create restore runbooks. Define RTO/RPO targets. Test disaster recovery scenarios. Train team on restore procedures.",
                    "status": "pending",
                },
            ]
            tasks_to_update.append(task)

        elif task["id"] == 47:  # Local screenshot capture (Playwright)
            task["subtasks"] = [
                {
                    "id": 1,
                    "title": "Set up Playwright infrastructure",
                    "description": "Install and configure Playwright for headless browser automation",
                    "dependencies": [],
                    "details": "Install Playwright with required browsers. Configure for headless operation. Set up browser pool management. Optimize for container deployment. Handle browser crashes gracefully.",
                    "status": "pending",
                },
                {
                    "id": 2,
                    "title": "Implement screenshot capture API",
                    "description": "Create API wrapper for Playwright screenshot functionality",
                    "dependencies": [1],
                    "details": "Match existing ScreenshotOne API interface. Implement viewport and device emulation. Add screenshot quality options. Support full-page captures. Include mobile viewport support.",
                    "status": "pending",
                },
                {
                    "id": 3,
                    "title": "Build performance optimization layer",
                    "description": "Optimize screenshot generation for scale and speed",
                    "dependencies": [2],
                    "details": "Implement browser instance pooling. Add request queuing and throttling. Create caching for repeated screenshots. Optimize image compression. Monitor resource usage.",
                    "status": "pending",
                },
                {
                    "id": 4,
                    "title": "Create error handling and retry logic",
                    "description": "Implement robust error handling for screenshot failures",
                    "dependencies": [2],
                    "details": "Handle timeout errors gracefully. Implement exponential backoff retries. Add fallback for problematic sites. Log detailed error information. Create failure analytics.",
                    "status": "pending",
                },
                {
                    "id": 5,
                    "title": "Migration and testing",
                    "description": "Migrate from ScreenshotOne and validate functionality",
                    "dependencies": [1, 2, 3, 4],
                    "details": "Create migration plan from ScreenshotOne. Run parallel comparison tests. Verify screenshot quality parity. Test at production scale. Monitor cost savings.",
                    "status": "pending",
                },
            ]
            tasks_to_update.append(task)

        elif task["id"] == 48:  # GPT-generated mockup
            task["subtasks"] = [
                {
                    "id": 1,
                    "title": "Design mockup generation prompts",
                    "description": "Create effective prompts for generating modern website mockups",
                    "dependencies": [],
                    "details": "Research modern web design trends. Create industry-specific prompt templates. Design prompts for different business types. Include brand guideline incorporation. Test prompt effectiveness.",
                    "status": "pending",
                },
                {
                    "id": 2,
                    "title": "Implement GPT API integration for mockups",
                    "description": "Build integration with GPT API for mockup generation",
                    "dependencies": [],
                    "details": "Set up GPT-4 API integration. Implement prompt engineering pipeline. Add response parsing and validation. Handle API rate limits. Create fallback strategies.",
                    "status": "pending",
                },
                {
                    "id": 3,
                    "title": "Create mockup rendering system",
                    "description": "Build system to convert GPT output to visual mockups",
                    "dependencies": [2],
                    "details": "Convert GPT descriptions to HTML/CSS. Implement template-based rendering. Add responsive design support. Create mockup preview system. Support multiple layout options.",
                    "status": "pending",
                },
                {
                    "id": 4,
                    "title": "Build quality assurance pipeline",
                    "description": "Implement automated quality checks for generated mockups",
                    "dependencies": [3],
                    "details": "Check mockup visual quality. Verify responsive design. Validate accessibility standards. Test cross-browser compatibility. Add human review workflow for edge cases.",
                    "status": "pending",
                },
                {
                    "id": 5,
                    "title": "Integration and A/B testing",
                    "description": "Integrate with pipeline and test effectiveness",
                    "dependencies": [1, 2, 3, 4],
                    "details": "Integrate mockup generation into pipeline. Set up A/B tests for mockup variations. Track conversion metrics. Optimize based on performance. Document best practices.",
                    "status": "pending",
                },
            ]
            tasks_to_update.append(task)

        elif task["id"] == 50:  # CAN-SPAM compliance
            task["subtasks"] = [
                {
                    "id": 1,
                    "title": "Audit existing email templates for compliance",
                    "description": "Review all current templates against CAN-SPAM requirements",
                    "dependencies": [],
                    "details": "Check for unsubscribe links in all templates. Verify physical address inclusion. Review subject line accuracy. Check sender information. Document compliance gaps.",
                    "status": "pending",
                },
                {
                    "id": 2,
                    "title": "Implement unsubscribe system",
                    "description": "Build compliant unsubscribe functionality",
                    "dependencies": [],
                    "details": "Create one-click unsubscribe links. Build unsubscribe processing within 10 days. Add unsubscribe confirmation pages. Implement suppression list management. Create unsubscribe analytics.",
                    "status": "pending",
                },
                {
                    "id": 3,
                    "title": "Standardize template components",
                    "description": "Create reusable compliant template components",
                    "dependencies": [1],
                    "details": "Build standard footer with required elements. Create compliant header templates. Implement dynamic physical address insertion. Add required disclosure text. Ensure mobile responsiveness.",
                    "status": "pending",
                },
                {
                    "id": 4,
                    "title": "Create compliance validation system",
                    "description": "Build automated compliance checking for all emails",
                    "dependencies": [2, 3],
                    "details": "Implement pre-send compliance checks. Validate all required elements present. Check subject line compliance. Verify opt-out functionality. Block non-compliant sends.",
                    "status": "pending",
                },
                {
                    "id": 5,
                    "title": "Documentation and training",
                    "description": "Create compliance documentation and team training",
                    "dependencies": [1, 2, 3, 4],
                    "details": "Document CAN-SPAM requirements. Create compliance checklist. Train team on requirements. Set up compliance monitoring. Schedule regular compliance audits.",
                    "status": "pending",
                },
            ]
            tasks_to_update.append(task)

    # Write back to file
    with open(".taskmaster/tasks/tasks.json", "w") as f:
        json.dump(data, f, indent=2)

    for task in tasks_to_update:
        pass


if __name__ == "__main__":
    add_subtasks_for_complex_tasks()
