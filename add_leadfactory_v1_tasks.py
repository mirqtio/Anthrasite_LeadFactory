#!/usr/bin/env python3
import json
import os
from datetime import datetime


def add_leadfactory_v1_tasks():
    # Path to tasks.json
    tasks_file = ".taskmaster/tasks/tasks.json"

    # Read the current tasks.json
    with open(tasks_file) as f:
        data = json.load(f)

    # Get the highest task ID
    max_id = max([task["id"] for task in data["tasks"]], default=0)

    # Current timestamp
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Define all 20 tasks from the requirements document
    new_tasks = [
        {
            "id": max_id + 1,
            "title": "Skip modern sites (PageSpeed >= 90 and mobile responsive)",
            "description": "Implement filtering logic to skip scraping/processing modern sites with PageSpeed score >= 90 and mobile responsive design",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["backend", "scraper", "performance"],
            "details": "Implement site filtering to skip modern websites that don't need redesign:\n- Integrate with Google PageSpeed API to check site performance\n- Add mobile responsiveness detection logic\n- Skip sites with PageSpeed score >= 90 AND mobile responsive\n- Update scraper to check these conditions before processing\n- Add configuration for threshold values\n- Implement caching for PageSpeed results to avoid API limits",
            "test_strategy": "1. Unit tests for PageSpeed API integration\n2. Unit tests for mobile responsiveness detection\n3. Integration tests for filtering logic\n4. E2E tests with sample sites\n5. Performance tests for API rate limiting",
            "subtasks": [],
        },
        {
            "id": max_id + 2,
            "title": "Score gating for personalization (only outdatedness_score >= 70)",
            "description": "Implement score-based gating to only personalize sites with outdatedness_score >= 70",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["backend", "scoring", "personalization"],
            "details": "Add gating logic to personalization pipeline:\n- Only process sites with outdatedness_score >= 70 for personalization\n- Skip personalization for sites below threshold\n- Make threshold configurable\n- Update pipeline to check score before GPT personalization\n- Add metrics to track gated vs processed sites\n- Ensure proper logging of skipped sites",
            "test_strategy": "1. Unit tests for score checking logic\n2. Integration tests with scoring engine\n3. E2E tests for complete pipeline flow\n4. Test threshold configuration\n5. Verify metrics collection",
            "subtasks": [],
        },
        {
            "id": max_id + 3,
            "title": "Drop non-performant verticals/geographies (blacklist implementation)",
            "description": "Implement blacklist system to filter out non-performant verticals and geographic regions",
            "status": "pending",
            "priority": "medium",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["backend", "filtering", "configuration"],
            "details": "Create blacklist system for filtering:\n- Implement vertical blacklist (e.g., certain business types)\n- Implement geographic blacklist (cities, states, regions)\n- Make blacklists configurable via YAML/JSON\n- Add pipeline filtering based on blacklists\n- Include override mechanisms for special cases\n- Add metrics for filtered records",
            "test_strategy": "1. Unit tests for blacklist loading and parsing\n2. Unit tests for filtering logic\n3. Integration tests with pipeline\n4. Test configuration updates\n5. Verify metrics and logging",
            "subtasks": [],
        },
        {
            "id": max_id + 4,
            "title": "Extract and store city/state from business address",
            "description": "Parse business addresses to extract and store city and state information separately",
            "status": "pending",
            "priority": "medium",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["backend", "data-processing", "database"],
            "details": "Implement address parsing and storage:\n- Parse full addresses to extract city and state\n- Handle various address formats\n- Store city and state as separate database fields\n- Update existing records with parsed data\n- Add validation for city/state data\n- Handle edge cases (PO boxes, missing data, etc.)",
            "test_strategy": "1. Unit tests for address parsing logic\n2. Test various address formats\n3. Database migration tests\n4. Data validation tests\n5. Edge case handling tests",
            "subtasks": [],
        },
        {
            "id": max_id + 5,
            "title": "Yelp and Google JSON retention decision",
            "description": "Implement decision logic for retaining or discarding Yelp and Google API JSON responses",
            "status": "pending",
            "priority": "low",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["backend", "storage", "data-retention"],
            "details": "Design and implement JSON retention strategy:\n- Analyze which fields from Yelp/Google JSON are needed long-term\n- Implement selective retention (keep only necessary fields)\n- Add compression for stored JSON data\n- Set up retention policies (how long to keep)\n- Create cleanup jobs for old data\n- Consider cost implications of storage",
            "test_strategy": "1. Unit tests for JSON filtering logic\n2. Compression/decompression tests\n3. Retention policy tests\n4. Cleanup job tests\n5. Storage cost analysis",
            "subtasks": [],
        },
        {
            "id": max_id + 6,
            "title": "DB nightly backup + off-site sync",
            "description": "Implement automated nightly database backups with off-site synchronization",
            "status": "pending",
            "priority": "high",
            "type": "infrastructure",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["database", "backup", "infrastructure"],
            "details": "Set up comprehensive backup system:\n- Configure nightly automated backups\n- Implement off-site sync (S3, Google Cloud Storage, etc.)\n- Add backup verification and integrity checks\n- Set up retention policies for backups\n- Create restore procedures and documentation\n- Add monitoring and alerting for backup failures",
            "test_strategy": "1. Test backup creation process\n2. Verify backup integrity\n3. Test restore procedures\n4. Verify off-site sync\n5. Test failure alerting",
            "subtasks": [],
        },
        {
            "id": max_id + 7,
            "title": "Local screenshot capture (replace ScreenshotOne with Playwright)",
            "description": "Replace ScreenshotOne API with local Playwright-based screenshot capture",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["backend", "screenshot", "cost-reduction"],
            "details": "Implement Playwright screenshot system:\n- Set up Playwright for headless browser automation\n- Replace ScreenshotOne API calls with Playwright\n- Handle browser pool management for performance\n- Implement retry logic for failed screenshots\n- Add screenshot quality and size optimization\n- Ensure compatibility with existing pipeline",
            "test_strategy": "1. Unit tests for Playwright wrapper\n2. Screenshot quality comparison tests\n3. Performance benchmarking\n4. Error handling tests\n5. Integration tests with pipeline",
            "subtasks": [],
        },
        {
            "id": max_id + 8,
            "title": "GPT-generated mockup (modernized site)",
            "description": "Implement GPT-based generation of modernized website mockups",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["backend", "ai", "mockup"],
            "details": "Create GPT-powered mockup generation:\n- Design prompts for modern website generation\n- Integrate with GPT API for mockup creation\n- Implement template-based approach for consistency\n- Add style guidelines and branding rules\n- Handle different business types and industries\n- Ensure mockups are realistic and appealing",
            "test_strategy": "1. Prompt engineering tests\n2. API integration tests\n3. Mockup quality validation\n4. A/B testing different approaches\n5. Performance and cost monitoring",
            "subtasks": [],
        },
        {
            "id": max_id + 9,
            "title": "Email thumbnail image",
            "description": "Generate and embed thumbnail images in marketing emails",
            "status": "pending",
            "priority": "medium",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [max_id + 8],
            "tags": ["email", "frontend", "marketing"],
            "details": "Implement email thumbnail system:\n- Generate thumbnail from mockup image\n- Optimize thumbnail size for email\n- Embed thumbnail in email template\n- Ensure compatibility with email clients\n- Add fallback for clients that block images\n- Track thumbnail engagement metrics",
            "test_strategy": "1. Thumbnail generation tests\n2. Email client compatibility tests\n3. Image optimization tests\n4. Fallback rendering tests\n5. Engagement tracking tests",
            "subtasks": [],
        },
        {
            "id": max_id + 10,
            "title": "Standardize template usage (CAN-SPAM compliance)",
            "description": "Ensure all email templates are CAN-SPAM compliant with standardized elements",
            "status": "pending",
            "priority": "high",
            "type": "compliance",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["email", "compliance", "legal"],
            "details": "Implement CAN-SPAM compliance:\n- Add required unsubscribe links to all templates\n- Include physical mailing address\n- Ensure accurate 'From' information\n- Add clear subject lines (no deception)\n- Implement opt-out processing within 10 days\n- Create compliance checklist and validation",
            "test_strategy": "1. Template compliance validation tests\n2. Unsubscribe link functionality tests\n3. Opt-out processing tests\n4. Compliance audit tests\n5. Legal review of templates",
            "subtasks": [],
        },
        {
            "id": max_id + 11,
            "title": "Bounce tracking + IP pool warm-up automation",
            "description": "Implement email bounce tracking and automated IP pool warm-up process",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["email", "deliverability", "automation"],
            "details": "Build comprehensive email deliverability system:\n- Implement bounce webhook processing\n- Track hard and soft bounces separately\n- Create IP warm-up schedule and automation\n- Implement gradual volume increase for new IPs\n- Add reputation monitoring and alerts\n- Create fallback strategies for deliverability issues",
            "test_strategy": "1. Bounce webhook processing tests\n2. Warm-up schedule validation\n3. Volume throttling tests\n4. Reputation monitoring tests\n5. Integration tests with email provider",
            "subtasks": [],
        },
        {
            "id": max_id + 12,
            "title": "Retarget email recipients",
            "description": "Implement retargeting system for email campaign recipients",
            "status": "pending",
            "priority": "medium",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["email", "marketing", "analytics"],
            "details": "Create email retargeting capabilities:\n- Track email opens and clicks\n- Segment recipients based on engagement\n- Create retargeting campaigns for engaged users\n- Implement follow-up email sequences\n- Add conversion tracking\n- Create reporting for retargeting effectiveness",
            "test_strategy": "1. Engagement tracking tests\n2. Segmentation logic tests\n3. Campaign automation tests\n4. Conversion tracking tests\n5. Reporting accuracy tests",
            "subtasks": [],
        },
        {
            "id": max_id + 13,
            "title": "Replace placeholder audit PDF",
            "description": "Create professional, data-driven audit PDF reports to replace placeholder version",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["reporting", "pdf", "frontend"],
            "details": "Develop comprehensive audit PDF:\n- Design professional PDF template\n- Include actual audit data and scores\n- Add visualizations and charts\n- Implement dynamic content based on business data\n- Ensure consistent branding\n- Optimize PDF size and generation time",
            "test_strategy": "1. PDF generation tests\n2. Data accuracy validation\n3. Visual regression tests\n4. Performance benchmarking\n5. Cross-platform compatibility tests",
            "subtasks": [],
        },
        {
            "id": max_id + 14,
            "title": "30-day access window for report download",
            "description": "Implement time-limited access system for report downloads with 30-day window",
            "status": "pending",
            "priority": "medium",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["security", "backend", "reporting"],
            "details": "Create secure time-limited access:\n- Generate unique, time-limited download links\n- Implement 30-day expiration for links\n- Add download tracking and analytics\n- Create reminder emails before expiration\n- Implement secure token generation\n- Add option to extend access if needed",
            "test_strategy": "1. Token generation and validation tests\n2. Expiration logic tests\n3. Security penetration tests\n4. Reminder email tests\n5. Access extension tests",
            "subtasks": [],
        },
        {
            "id": max_id + 15,
            "title": "Support local PDF delivery",
            "description": "Add option to deliver PDFs directly without requiring download links",
            "status": "pending",
            "priority": "low",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [max_id + 13],
            "tags": ["reporting", "pdf", "delivery"],
            "details": "Implement direct PDF delivery:\n- Add option to attach PDF to emails\n- Implement size limits and compression\n- Create delivery preference settings\n- Handle email provider limitations\n- Add fallback to download link for large files\n- Track delivery success rates",
            "test_strategy": "1. Email attachment tests\n2. Size limit handling tests\n3. Compression quality tests\n4. Delivery tracking tests\n5. Fallback mechanism tests",
            "subtasks": [],
        },
        {
            "id": max_id + 16,
            "title": "Add per-service daily spend caps",
            "description": "Implement daily spending limits for each external service (APIs, etc.)",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["cost-control", "backend", "monitoring"],
            "details": "Create comprehensive spend control:\n- Track costs for each external service\n- Implement configurable daily caps\n- Add real-time spend monitoring\n- Create automatic throttling when approaching limits\n- Add alerts for high spend rates\n- Implement emergency shutdown procedures",
            "test_strategy": "1. Cost tracking accuracy tests\n2. Cap enforcement tests\n3. Throttling logic tests\n4. Alert system tests\n5. Emergency shutdown tests",
            "subtasks": [],
        },
        {
            "id": max_id + 17,
            "title": "Add ~10% buffer cost and 10% reserve withholding on profit",
            "description": "Implement financial safeguards with cost buffer and profit reserve",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["financial", "cost-control", "reporting"],
            "details": "Implement financial safety measures:\n- Add 10% buffer to all cost calculations\n- Implement 10% profit withholding for reserves\n- Update financial reporting to show buffers\n- Create reserve fund tracking\n- Add configurable buffer percentages\n- Ensure accurate profit calculations with buffers",
            "test_strategy": "1. Buffer calculation tests\n2. Profit withholding tests\n3. Financial reporting accuracy tests\n4. Reserve tracking tests\n5. Configuration flexibility tests",
            "subtasks": [],
        },
        {
            "id": max_id + 18,
            "title": "Enrich funnel model to support agency lead track",
            "description": "Extend the funnel model to track and support agency-specific lead flows",
            "status": "pending",
            "priority": "medium",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["analytics", "backend", "agency"],
            "details": "Enhance funnel for agency tracking:\n- Add agency-specific lead sources\n- Create separate funnel stages for agencies\n- Implement agency attribution tracking\n- Add agency-specific conversion metrics\n- Create agency dashboard views\n- Support multi-touch attribution for agencies",
            "test_strategy": "1. Agency attribution tests\n2. Funnel stage tracking tests\n3. Conversion metric tests\n4. Dashboard functionality tests\n5. Multi-touch attribution tests",
            "subtasks": [],
        },
        {
            "id": max_id + 19,
            "title": "Tag leads by origin source and stage",
            "description": "Implement comprehensive lead tagging system for source and stage tracking",
            "status": "pending",
            "priority": "high",
            "type": "feature",
            "created_at": timestamp,
            "dependencies": [],
            "tags": ["analytics", "backend", "tracking"],
            "details": "Create lead tagging system:\n- Tag leads with origin source (organic, paid, referral, etc.)\n- Track lead stage in pipeline\n- Implement tag-based filtering and reporting\n- Add UTM parameter tracking\n- Create tag analytics and insights\n- Enable bulk tagging operations",
            "test_strategy": "1. Tagging logic tests\n2. Source attribution tests\n3. Stage tracking tests\n4. Filtering functionality tests\n5. Analytics accuracy tests",
            "subtasks": [],
        },
        {
            "id": max_id + 20,
            "title": "Add test coverage to reflect above changes",
            "description": "Comprehensive test suite additions for all new LeadFactory v1.0 features",
            "status": "pending",
            "priority": "high",
            "type": "testing",
            "created_at": timestamp,
            "dependencies": list(
                range(max_id + 1, max_id + 20)
            ),  # Depends on all other tasks
            "tags": ["testing", "quality", "ci-cd"],
            "details": "Expand test coverage for all features:\n- Add unit tests for each new component\n- Create integration tests for feature interactions\n- Implement E2E tests for complete workflows\n- Add performance and load tests\n- Ensure minimum 80% code coverage\n- Update CI pipeline with all new tests",
            "test_strategy": "1. Unit test implementation for all features\n2. Integration test scenarios\n3. E2E workflow validation\n4. Performance benchmarking\n5. Coverage analysis and gap filling",
            "subtasks": [],
        },
    ]

    # Add all new tasks
    data["tasks"].extend(new_tasks)

    # Write back to file
    with open(tasks_file, "w") as f:
        json.dump(data, f, indent=2)

    for task in new_tasks:
        f" (depends on: {task['dependencies']})" if task["dependencies"] else ""


if __name__ == "__main__":
    add_leadfactory_v1_tasks()
