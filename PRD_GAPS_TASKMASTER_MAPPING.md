# PRD Gap Analysis - TaskMaster Mapping

## Summary
After analyzing the PRD requirements against the current implementation and TaskMaster tasks, here's the status:

## Existing TaskMaster Tasks for PRD Gaps

### 1. Modern Site Filtering - Task #41 (PENDING)
- **Title**: "Skip Modern Sites in Lead Funnel"
- **Status**: Pending
- **PRD Requirement**: Filter sites with PageSpeed >= 90 and mobile responsive
- **Priority**: HIGH - This is marked as "first priority in implementation order"

### 2. PageSpeed Integration - Subtask of #42 (PENDING)
- **Title**: "Implement PageSpeed Insights check in the enrichment step"
- **Status**: Pending (part of task #42)
- **Dependency**: Follows task #41

### 3. Per-Service Cost Caps - Task #60 (COMPLETED)
- **Title**: "Enforce Per-Service Daily Cost Caps"
- **Status**: Completed ✅
- **Implementation**: MAX_DOLLARS_LLM, MAX_DOLLARS_SEMRUSH environment variables

## Gaps NOT in TaskMaster

### 1. SEMrush Bulk Metrics API Integration
- **PRD Requirement**: Batch 50 URLs → SEMrush 'Bulk Metrics' for old CMS, missing schema, DA < 20
- **Current State**: Cost tracking exists but no API client
- **Action Needed**: Create new TaskMaster task

### 2. WeasyPrint PDF Generation
- **PRD Requirement**: WeasyPrint HTML→PDF
- **Current State**: Using ReportLab instead
- **Action Needed**: Decision required - keep ReportLab or migrate?

### 3. PostgreSQL Backup with rsync
- **PRD Requirement**: Nightly pg_dump to SSD and rsync to NAS
- **Current State**: Generic backup exists, missing PostgreSQL-specific
- **Action Needed**: Create new TaskMaster task

## Recommended Actions

### 1. Prioritize Existing Pending Tasks
Start with Task #41 (Skip Modern Sites) as it's marked as first priority and blocks other work.

### 2. Create New TaskMaster Tasks

#### New Task: SEMrush Bulk Metrics Integration
```json
{
  "id": 61,
  "title": "Implement SEMrush Bulk Metrics API Integration",
  "description": "Create SEMrush API client for batch URL analysis to detect old CMS, missing schema, and domain authority < 20",
  "priority": "high",
  "dependencies": [42],
  "details": "Implement SEMrushClient class with batch processing (50 URLs), integrate into enrichment pipeline after PageSpeed, add cost tracking per API call, handle rate limits with exponential backoff",
  "testStrategy": "1. Unit tests for API client with mocked responses\n2. Integration tests with test account\n3. Cost tracking verification\n4. Rate limit handling tests"
}
```

#### New Task: PostgreSQL Backup Implementation
```json
{
  "id": 62,
  "title": "Implement PostgreSQL Nightly Backup with rsync",
  "description": "Create automated nightly pg_dump backup to attached SSD with rsync to off-site NAS",
  "priority": "medium",
  "dependencies": [],
  "details": "Create backup script using pg_dump, configure cron for nightly execution, implement rsync to NAS, add monitoring for backup failures, document restore procedures",
  "testStrategy": "1. Test backup script execution\n2. Verify rsync functionality\n3. Test restore from backup\n4. Verify monitoring alerts"
}
```

## Implementation Order

1. **Task #41** - Skip Modern Sites (PENDING) - Critical for cost savings
2. **Task #42** - PageSpeed Integration (PENDING) - Enables #41
3. **New Task #61** - SEMrush Integration - Enhanced enrichment
4. **New Task #62** - PostgreSQL Backup - Production readiness

## Notes

- Task #60 (Per-Service Cost Caps) is already completed ✅
- Consider keeping ReportLab instead of migrating to WeasyPrint (minimal benefit)
- The core pipeline is ~85% complete with these gaps representing ~7-10 days of work
