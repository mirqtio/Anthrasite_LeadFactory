# Gap Analysis Tasks Summary

Based on the gap analysis in changes.md, 13 new tasks have been added to address implementation gaps.

## Prescribed Implementation Order (from changes.md)

All tasks are set to high priority and must be implemented in the following sequence:

1. **[41] Skip Modern Sites in Lead Funnel** (4 hours) - Filter sites with PageSpeed >= 90
2. **[42] Parse and Store City/State** (2 hours) - Extract city/state from business address
3. **[43] Decide & Implement Yelp JSON Retention** (6 hours) - Privacy/retention policy
4. **[44] Implement Local Screenshot Capture** (8 hours) - Playwright fallback ⚠️ Complex
5. **[45] Embed Website Thumbnail in Email** (4 hours) - Include screenshot in emails (depends on #44)
6. **[46] Apply Outdatedness Score Threshold** (6 hours) - Only personalize score >= 70%
7. **[47] Integrate AI Content with Email Template** (8 hours) - CAN-SPAM compliance
8. **[48] Auto-Monitor Bounce Rate & IP Warmup** (6 hours) - Switch IP pools >2% ⚠️ Complex
9. **[49] Generate Real Audit PDF Content** (16 hours) - Replace placeholder ⚠️ Complex
10. **[50] Extend Report Link Expiry** (1 hour) - Change from 72 to 720 hours
11. **[51] Support Local PDF Delivery** (8 hours) - Alternative to cloud storage (depends on #49)
12. **[52] Enforce Per-Service Daily Cost Caps** (6 hours) - LLM/SEMrush spend limits
13. **[53] Implement Nightly DB Backup** (3 hours) - Add pg_dump and off-site sync

## Complexity Analysis Results

Three tasks were identified as highly complex and expanded with subtasks:
- Task 49 (Audit PDF) - Complexity score 8 - 6 subtasks added
- Task 44 (Screenshot) - Complexity score 7 - 5 subtasks added
- Task 48 (Bounce Monitor) - Complexity score 7 - 5 subtasks added

## Implementation Timeline

Following the prescribed order with sequential dependencies:
- **Phase 1** (Tasks 41-43): 12 hours - Basic infrastructure fixes
- **Phase 2** (Tasks 44-48): 32 hours - Core feature implementation
- **Phase 3** (Tasks 49-51): 25 hours - Report generation and delivery
- **Phase 4** (Tasks 52-53): 9 hours - Cost control and operations

Total estimated effort: 78 hours
