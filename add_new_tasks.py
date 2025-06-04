#!/usr/bin/env python3
import json
import sys


def add_new_tasks():
    # Read the current tasks.json
    with open("tasks/tasks.json") as f:
        data = json.load(f)

    # New task 33: Stripe fee & tax tracking
    task_33 = {
        "id": 33,
        "title": "Stripe fee & tax tracking in BudgetGuard",
        "description": "Implement comprehensive Stripe fee and tax tracking for profit reporting in the audit-first business model",
        "status": "pending",
        "priority": "high",
        "type": "feature",
        "created_at": "2025-06-03T09:53:00Z",
        "dependencies": [],
        "tags": ["cost_model"],
        "details": "Implement Stripe webhook integration and fee tracking for the $99 audit report business model:\n- Listen to Stripe webhooks for successful payment events\n- Extract and store fee, tax, and net amounts for every transaction\n- Integrate fee data into the daily cost aggregation system\n- Update profit reporting to show:\n  * Subtotal revenue & cost before agency fees\n  * Incremental agency revenue & cost (future phase)\n  * Grand totals with accurate net margins\n- Update Grafana dashboard with new visualizations:\n  * Stripe fees per day graph\n  * Gross vs. Net margin comparison\n- Ensure all financial data is accurately tracked for business intelligence",
        "test_strategy": "1. Unit tests for webhook processing and fee calculation\n2. Integration tests with Stripe test webhooks\n3. E2E tests for complete payment flow and reporting\n4. Test execution and issue resolution\n5. CI pipeline updates\n6. Deployment verification",
        "subtasks": [
            {
                "id": 1,
                "title": "Implement Stripe webhook listener and processing",
                "description": "Set up webhook endpoint to receive and process Stripe payment events",
                "dependencies": [],
                "details": "Create secure webhook endpoint to receive Stripe payment_intent.succeeded events. Implement signature verification for security. Parse webhook payload to extract transaction details including fees, taxes, and net amounts. Handle webhook retries and idempotency. Add comprehensive error handling and logging.",
                "status": "pending",
            },
            {
                "id": 2,
                "title": "Integrate fee data into cost aggregation system",
                "description": "Modify daily cost aggregation to include Stripe fees and taxes",
                "dependencies": [1],
                "details": "Update the existing cost tracking system to incorporate Stripe transaction fees and taxes. Modify database schema if needed to store fee breakdowns. Ensure fee data is properly categorized and aggregated in daily reports. Maintain backward compatibility with existing cost tracking.",
                "status": "pending",
            },
            {
                "id": 3,
                "title": "Update profit reporting with fee breakdowns",
                "description": "Enhance profit reports to show revenue and cost breakdowns",
                "dependencies": [2],
                "details": "Modify profit reporting logic to display subtotal revenue & cost before agency fees, space for incremental agency revenue & cost (future), and grand totals. Ensure accurate net margin calculations. Update report formats and APIs to include new breakdown structure.",
                "status": "pending",
            },
            {
                "id": 4,
                "title": "Create Grafana dashboard visualizations",
                "description": "Add new graphs for Stripe fees and margin analysis",
                "dependencies": [2, 3],
                "details": "Create two new Grafana dashboard panels: (a) Stripe fees per day showing daily fee trends, (b) Gross vs. Net margin comparison showing the impact of fees on profitability. Configure proper time ranges, aggregations, and visual styling consistent with existing dashboards.",
                "status": "pending",
            },
            {
                "id": 5,
                "title": "Comprehensive testing and deployment",
                "description": "Complete testing suite and CI integration",
                "dependencies": [1, 2, 3, 4],
                "details": "Create comprehensive unit tests for webhook processing and fee calculations. Develop integration tests with Stripe test environment. Implement e2e tests covering complete payment flow and reporting. Run all tests and resolve any issues. Update CI pipeline with new tests. Merge to master and confirm successful deployment via GitHub CLI logs.",
                "status": "pending",
            },
        ],
    }

    # New task 34: SendGrid dedicated-IP warm-up scheduler
    task_34 = {
        "id": 34,
        "title": "SendGrid dedicated-IP warm-up scheduler",
        "description": "Implement dedicated IP warm-up system for 110k daily cold email volume with automated throttling and bounce integration",
        "status": "pending",
        "priority": "high",
        "type": "feature",
        "created_at": "2025-06-03T09:53:00Z",
        "dependencies": [],
        "details": "Implement a comprehensive SendGrid dedicated IP warm-up system for high-volume cold email sending:\n- Move from shared IP pool to dedicated IP(s) for 110k daily emails\n- Implement 14-day warm-up schedule with automated send-cap progression\n- Create send-cap table (5k, 15k, 35k, etc.) with automatic throttling\n- Integrate with existing bounce-rate rotation logic post warm-up\n- Surface warm-up progress and metrics in monitoring dashboard\n- Ensure compliance with SendGrid best practices and deliverability standards\n- Handle failover scenarios and warm-up interruptions gracefully",
        "test_strategy": "1. Unit tests for warm-up scheduling and throttling logic\n2. Integration tests with SendGrid API and bounce monitoring\n3. E2E tests for complete warm-up cycle simulation\n4. Test execution and issue resolution\n5. CI pipeline updates\n6. Deployment verification",
        "subtasks": [
            {
                "id": 1,
                "title": "Design and implement warm-up schedule system",
                "description": "Create the core warm-up scheduling and progression logic",
                "dependencies": [],
                "details": "Design 14-day warm-up schedule with progressive send caps (5k, 15k, 35k, 50k, 75k, 100k, 110k). Implement scheduling system that automatically advances through warm-up stages. Create configuration system for send caps and timing. Include safety mechanisms to prevent exceeding daily limits and handle schedule interruptions.",
                "status": "pending",
            },
            {
                "id": 2,
                "title": "Implement SendGrid dedicated IP provisioning",
                "description": "Set up dedicated IP allocation and configuration with SendGrid",
                "dependencies": [],
                "details": "Integrate with SendGrid API to provision dedicated IP(s). Configure IP authentication and DNS records. Set up IP pool management for multiple IPs if needed. Implement IP health monitoring and status tracking. Create fallback mechanisms for IP provisioning failures.",
                "status": "pending",
            },
            {
                "id": 3,
                "title": "Create automated throttling system",
                "description": "Implement send-rate throttling based on warm-up schedule",
                "dependencies": [1, 2],
                "details": "Build throttling system that enforces daily send caps based on current warm-up stage. Implement rate limiting to distribute sends throughout the day. Create queue management for email batches. Add monitoring for send rates and cap adherence. Include emergency stop mechanisms for compliance.",
                "status": "pending",
            },
            {
                "id": 4,
                "title": "Integrate with bounce-rate rotation system",
                "description": "Connect warm-up system with existing IP rotation logic",
                "dependencies": [3],
                "details": "Modify existing bounce-rate monitoring and IP rotation system to work with dedicated IPs post warm-up. Update Task #21 dependency to be blocked by warm-up completion. Ensure seamless transition from warm-up to production rotation. Maintain bounce rate thresholds and rotation triggers.",
                "status": "pending",
            },
            {
                "id": 5,
                "title": "Build monitoring dashboard and metrics",
                "description": "Create comprehensive monitoring for warm-up progress and health",
                "dependencies": [1, 3],
                "details": "Develop dashboard showing warm-up progress, daily send volumes, success rates, and schedule adherence. Create metrics for IP reputation, deliverability rates, and warm-up health. Implement alerts for warm-up issues, schedule deviations, and deliverability problems. Surface progress in existing metrics dashboard.",
                "status": "pending",
            },
            {
                "id": 6,
                "title": "Comprehensive testing and deployment",
                "description": "Complete testing suite and CI integration",
                "dependencies": [1, 2, 3, 4, 5],
                "details": "Create comprehensive unit tests for scheduling and throttling logic. Develop integration tests with SendGrid API and bounce monitoring systems. Implement e2e tests simulating complete warm-up cycles. Run all tests and resolve any issues. Update CI pipeline with new tests. Merge to master and confirm successful deployment via GitHub CLI logs.",
                "status": "pending",
            },
        ],
    }

    # Add the new tasks
    data["tasks"].append(task_33)
    data["tasks"].append(task_34)

    # Write back to file
    with open("tasks/tasks.json", "w") as f:
        json.dump(data, f, indent=2)

    print("Added tasks 33 and 34 successfully!")


if __name__ == "__main__":
    add_new_tasks()
