# Pending Tasks Analysis

## Summary
Total pending tasks: 20

## Critical Priority Tasks (No Dependencies)
1. **Task 35: Fix Critical Test Coverage Gaps**
   - Priority: critical
   - Dependencies: None
   - Description: Add comprehensive tests for storage abstraction layer, CLI commands, and pipeline orchestration services.

2. **Task 36: Fix Security Vulnerabilities**
   - Priority: critical
   - Dependencies: None
   - Description: Address critical security issues including bare except blocks, missing input validation, hardcoded values, and potential SQL injection risks.

## High Priority Tasks - PRD Features Chain
The following tasks form a dependency chain for implementing PRD features:

3. **Task 41: Skip Modern Sites in Lead Funnel** ⭐ (PageSpeed Insights)
   - Priority: high
   - Dependencies: None
   - Description: If PageSpeed Insights shows performance >= 90 and mobile responsive, mark lead as processed without email.

4. **Task 42: Parse and Store City/State for Businesses** ⭐ (City/State Parsing)
   - Priority: high
   - Dependencies: [41]
   - Description: Extract city and state from business address and save to businesses table.

5. **Task 43: Decide & Implement Yelp JSON Retention**
   - Priority: high
   - Dependencies: [42]
   - Description: Determine retention policy for raw Yelp/Google API JSON.

6. **Task 44: Implement Local Screenshot Capture**
   - Priority: high
   - Dependencies: [43]
   - Description: Add Playwright fallback for screenshots when SCREENSHOT_ONE_KEY is not provided.

7. **Task 45: Embed Website Thumbnail in Email** ⭐ (Email Enhancement)
   - Priority: high
   - Dependencies: [44]
   - Description: Include screenshot thumbnail in email HTML as a small preview.

8. **Task 46: Apply Outdatedness Score Threshold**
   - Priority: high
   - Dependencies: [45]
   - Description: Only queue emails for leads scoring >= 70% outdatedness.

9. **Task 47: Integrate AI Content with Email Template**
   - Priority: high
   - Dependencies: [46]
   - Description: Use Jinja EmailTemplateEngine to inject GPT-generated content.

10. **Task 48: Auto-Monitor Bounce Rate & IP Warmup**
    - Priority: high
    - Dependencies: [47]
    - Description: Implement periodic bounce rate checks and IP pool switching.

11. **Task 49: Generate Real Audit PDF Content**
    - Priority: high
    - Dependencies: [48]
    - Description: Replace placeholder PDF with comprehensive audit report using metrics and GPT-4.

12. **Task 50: Extend Report Link Expiry to 30 Days**
    - Priority: high
    - Dependencies: [49]
    - Description: Increase expiry_hours from 72 to 720 hours.

13. **Task 51: Support Local PDF Delivery**
    - Priority: high
    - Dependencies: [49, 50]
    - Description: Add option to skip Supabase and deliver PDFs locally.

14. **Task 52: Enforce Per-Service Daily Cost Caps**
    - Priority: high
    - Dependencies: [51]
    - Description: Implement daily spend limits for LLM and SEMrush APIs.

15. **Task 53: Implement Nightly DB Backup**
    - Priority: high
    - Dependencies: [52]
    - Description: Add PostgreSQL backup to nightly.sh with off-site storage.

## High Priority Tasks - Independent
16. **Task 37: Complete Code Quality Improvements**
    - Priority: high
    - Dependencies: None
    - Description: Fix TODOs, replace prints with logging, add type hints.

17. **Task 38: Complete Microservices Migration**
    - Priority: high
    - Dependencies: None
    - Description: Finish transition to microservices architecture.

## Medium Priority Tasks
18. **Task 39: Create Comprehensive Documentation**
    - Priority: medium
    - Dependencies: None
    - Description: Add READMEs, API docs, installation guides.

19. **Task 40: Implement Performance Optimizations**
    - Priority: medium
    - Dependencies: [37]
    - Description: Replace sync with async, optimize queries, implement streaming.

20. **Task 55: Decide & Implement Yelp JSON Retention** (Duplicate of Task 43)
    - Priority: medium
    - Dependencies: None
    - Description: Same as Task 43 - retention policy for API JSON.

## Recommended Implementation Order

### Phase 1: Critical Issues (Parallel)
- Task 35: Fix Critical Test Coverage Gaps
- Task 36: Fix Security Vulnerabilities

### Phase 2: Independent High Priority (Parallel)
- Task 37: Complete Code Quality Improvements
- Task 38: Complete Microservices Migration

### Phase 3: PRD Features Chain (Sequential)
1. Task 41: Skip Modern Sites (PageSpeed Insights) ⭐
2. Task 42: Parse City/State ⭐
3. Task 43: Yelp JSON Retention
4. Task 44: Local Screenshot Capture
5. Task 45: Email Thumbnails ⭐
6. Task 46: Score Threshold
7. Task 47: AI Content Integration
8. Task 48: Bounce Monitoring
9. Task 49: Real Audit PDFs
10. Task 50: 30-Day Links
11. Task 51: Local PDF Delivery
12. Task 52: Cost Caps
13. Task 53: DB Backups

### Phase 4: Performance & Documentation
- Task 40: Performance Optimizations (depends on Task 37)
- Task 39: Documentation

## Notes
- Task 55 appears to be a duplicate of Task 43
- The PRD features chain (Tasks 41-53) forms the longest dependency path
- SEMrush integration is not explicitly mentioned but may be part of Task 49 (audit PDF generation)
