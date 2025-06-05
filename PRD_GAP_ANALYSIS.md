# PRD Gap Analysis - Anthrasite Lead Factory v1.0

## Executive Summary
Based on analysis of the PRD in changes.md against the current codebase, the implementation is approximately **85% complete**. Most core functionality is implemented, but critical gaps remain in the enrichment and filtering pipeline.

## Implementation Status Table

| Requirement | Status | Evidence | Gap Details | Effort |
|------------|--------|----------|-------------|--------|
| **4.1.1 Scrape SMB URLs** | ✅ | `leadfactory/pipeline/scrape.py` | Fully implemented with Yelp API | - |
| **4.1.2 Rule-out modern sites** | ❌ | Tests exist, no production code | Missing PageSpeed filtering logic | **M** |
| **4.1.3 SEO/tech-stack check** | ❌ | Config references only | No SEMrush API client | **L** |
| **4.1.4 Local HTML fetch** | ✅ | `leadfactory/pipeline/screenshot_local.py` | Playwright implemented | - |
| **4.1.5 Screenshot generation** | ✅ | `leadfactory/pipeline/screenshot_local.py` | Local Chrome implemented | - |
| **4.2 Scoring & personalization** | ✅ | `leadfactory/scoring/`, `unified_gpt4o.py` | YAML rules + GPT-4o | - |
| **4.3 Email delivery** | ✅ | `leadfactory/email/` | SendGrid with full tracking | - |
| **4.4 Payment & report** | ⚠️ | `leadfactory/services/` | Stripe ✅, PDF uses ReportLab not WeasyPrint | **S** |
| **4.5 Back-office & ops** | ⚠️ | `leadfactory/cost/`, `etc/` | Cost caps ✅, pg_dump missing | **S** |

## Critical Implementation Gaps

### 1. Google PageSpeed Insights Integration (Priority: HIGH)
**Requirement**: Filter out sites with `lighthouse_performance ≥ 90` AND `is_responsive = true`

**Current State**:
- Test file exists: `tests/api/test_pagespeed_api.py`
- No production implementation in enrichment pipeline

**Required Implementation**:
```python
# leadfactory/pipeline/pagespeed.py
class PageSpeedInsightsClient:
    def analyze_url(self, url: str) -> dict:
        # Call PSI API
        # Extract performance score and mobile friendliness
        # Return structured data
```

**Effort**: Medium (2-3 days)

### 2. SEMrush Bulk Metrics Integration (Priority: HIGH)
**Requirement**: Batch 50 URLs → SEMrush 'Bulk Metrics' to flag old CMS, missing schema, DA < 20

**Current State**:
- Cost tracking configured for SEMrush
- No API client implementation

**Required Implementation**:
```python
# leadfactory/integrations/semrush.py
class SEMrushBulkMetricsClient:
    def analyze_batch(self, urls: List[str]) -> List[dict]:
        # Batch process URLs
        # Extract CMS, schema, DA metrics
        # Return enriched data
```

**Effort**: Large (3-4 days)

### 3. Modern Site Filtering Logic (Priority: CRITICAL)
**Requirement**: Exclude sites that pass modern criteria before personalization

**Current State**: No implementation found

**Required Implementation**:
```python
# leadfactory/pipeline/filter_modern.py
def should_exclude_site(business: dict) -> bool:
    if business.get('lighthouse_performance', 0) >= 90:
        if business.get('is_responsive', False):
            return True
    return False
```

**Effort**: Small (1 day)

### 4. WeasyPrint vs ReportLab (Priority: LOW)
**Requirement**: PRD specifies WeasyPrint for HTML→PDF

**Current State**: Using ReportLab instead

**Decision Needed**: Is ReportLab acceptable or must migrate to WeasyPrint?

**Effort**: Small if keeping ReportLab, Medium if migrating

### 5. PostgreSQL Backup with rsync (Priority: MEDIUM)
**Requirement**: Nightly `pg_dump` to attached SSD and rsync to off-site NAS

**Current State**: Generic backup service exists, missing PostgreSQL-specific implementation

**Required Implementation**:
```bash
# scripts/backup_postgres.sh
pg_dump $DATABASE_URL > /backup/$(date +%Y%m%d).sql
rsync -av /backup/ nas.local:/backups/anthrasite/
```

**Effort**: Small (1 day)

## Recommended Task List (Ordered by Priority)

### Task 1: Implement PageSpeed Insights Filtering
```json
{
  "id": "prd-gap-1",
  "title": "Implement Google PageSpeed Insights integration for modern site filtering",
  "priority": "critical",
  "effort": "M",
  "dependencies": [],
  "acceptance_criteria": [
    "Create PageSpeedInsightsClient in leadfactory/integrations/",
    "Add to enrichment pipeline after scraping",
    "Filter sites with performance ≥ 90 AND is_responsive = true",
    "Add unit and integration tests",
    "Update scoring engine to use PSI data"
  ]
}
```

### Task 2: Implement SEMrush Bulk Metrics
```json
{
  "id": "prd-gap-2",
  "title": "Implement SEMrush Bulk Metrics API integration",
  "priority": "high",
  "effort": "L",
  "dependencies": ["prd-gap-1"],
  "acceptance_criteria": [
    "Create SEMrushClient with batch processing",
    "Integrate into enrichment pipeline",
    "Extract old_CMS, missing_schema, DA metrics",
    "Add cost tracking per API call",
    "Implement exponential backoff for rate limits"
  ]
}
```

### Task 3: Create Modern Site Filter
```json
{
  "id": "prd-gap-3",
  "title": "Implement modern site filtering logic in pipeline",
  "priority": "critical",
  "effort": "S",
  "dependencies": ["prd-gap-1"],
  "acceptance_criteria": [
    "Create filter_modern_sites() function",
    "Integrate after enrichment, before personalization",
    "Log filtered sites with reasons",
    "Add metrics for filter effectiveness",
    "Create unit tests for filter logic"
  ]
}
```

### Task 4: Implement PostgreSQL Backup
```json
{
  "id": "prd-gap-4",
  "title": "Implement nightly PostgreSQL backup with rsync",
  "priority": "medium",
  "effort": "S",
  "dependencies": [],
  "acceptance_criteria": [
    "Create backup script with pg_dump",
    "Configure cron for nightly execution",
    "Implement rsync to NAS",
    "Add monitoring and alerts for backup failures",
    "Test restore procedure"
  ]
}
```

### Task 5: Evaluate PDF Generation Library
```json
{
  "id": "prd-gap-5",
  "title": "Evaluate ReportLab vs WeasyPrint for PDF generation",
  "priority": "low",
  "effort": "S",
  "dependencies": [],
  "acceptance_criteria": [
    "Document pros/cons of current ReportLab implementation",
    "Test WeasyPrint with sample reports",
    "Make go/no-go decision on migration",
    "Update PRD if keeping ReportLab"
  ]
}
```

## Summary

The codebase is well-architected and most core functionality is implemented. The critical gaps are:

1. **PageSpeed Insights integration** - Essential for filtering modern sites
2. **SEMrush API integration** - Required for SEO/tech-stack analysis
3. **Modern site filtering logic** - Core business requirement

These gaps represent approximately 7-10 days of development effort. Once implemented, the system will meet all PRD requirements for the v1.0 local-stack launch.

## Next Steps

1. Prioritize PageSpeed Insights integration (blocks filtering logic)
2. Implement modern site filter to reduce wasted personalization costs
3. Add SEMrush for richer enrichment data
4. Set up PostgreSQL backups for production readiness
5. Make decision on PDF library (recommend keeping ReportLab)
