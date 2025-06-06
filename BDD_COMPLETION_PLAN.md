# BDD Features 1-8 Completion Plan

This document outlines the specific tasks needed to complete BDD scenarios for Features 1-8, bringing coverage from 77% to 95%+.

---

## 🎯 **FEATURE 1: Lead Acquisition & Enrichment** (80% → 95%)

### **Missing Scenarios to Implement:**

#### **LA-2: Missing Yelp Key Validation**
```gherkin
Given Yelp key is blank When "Acquire" clicked Then system blocks action and shows ENV001 guidance
```

**Implementation Tasks:**
- [ ] Add pre-flight API key validation in scraper
- [ ] Create ENV001 error code and guidance message
- [ ] Add UI blocking when keys missing
- [ ] Write integration test for key validation

**Files to Modify:**
- `leadfactory/pipeline/scrape.py` - Add key validation
- `leadfactory/cli/commands/pipeline_commands.py` - Add validation to CLI
- `tests/integration/test_api_key_validation.py` - New test file

#### **LA-5: Manual Reject Functionality**
```gherkin
Given lead list contains irrelevant business When user ticks checkbox & presses "Reject selected" Then record is archived and hidden from default view
```

**Implementation Tasks:**
- [ ] Add bulk reject API endpoint
- [ ] Create reject UI in dashboard
- [ ] Add archive status to business records
- [ ] Filter archived businesses from default views

**Files to Modify:**
- `leadfactory/api/business_management_api.py` - New file
- `leadfactory/static/dashboard.html` - Add bulk actions
- `leadfactory/storage/postgres_storage.py` - Add archive functionality

**Estimated Time:** 2 days

---

## 🎯 **FEATURE 2: Website/GBP Analysis & Scoring** (85% → 95%)

### **Missing Scenarios to Implement:**

#### **AN-2: ScreenshotOne Retry Logic**
```gherkin
Given first ScreenshotOne call times out When auto-retry runs Then image saved and AI check continues
```

**Implementation Tasks:**
- [ ] Enhance retry mechanism in screenshot module
- [ ] Add exponential backoff for ScreenshotOne API
- [ ] Improve error logging and recovery
- [ ] Add retry status tracking

**Files to Modify:**
- `leadfactory/pipeline/screenshot.py` - Enhance retry logic
- `leadfactory/pipeline/error_handling.py` - Add screenshot-specific handling

#### **AN-3: AI JSON Malformed Handling**
```gherkin
Given LLM returns invalid JSON When parser errors Then fallback path marks "AI-Uncertain" and score weight set to 0
```

**Implementation Tasks:**
- [ ] Add JSON validation for LLM responses
- [ ] Create "AI-Uncertain" status
- [ ] Implement fallback scoring when AI fails
- [ ] Add logging for malformed responses

**Files to Modify:**
- `leadfactory/pipeline/unified_gpt4o.py` - Add JSON validation
- `leadfactory/scoring/scoring_engine.py` - Add fallback scoring

**Estimated Time:** 1 day

---

## 🎯 **FEATURE 3: Visual Mockup Generation & QA** (70% → 90%)

### **Missing Scenarios to Implement:**

#### **MU-3: Human QA Override**
```gherkin
Given AI QA score <5 When human opens QA modal and revises prompt Then regenerated concept re-evaluated
```

**Implementation Tasks:**
- [ ] Create QA modal UI component
- [ ] Add human override API endpoints
- [ ] Implement prompt revision workflow
- [ ] Add re-evaluation trigger

**Files to Create:**
- `leadfactory/api/mockup_qa_api.py` - QA management endpoints
- `leadfactory/static/mockup_qa_modal.html` - QA interface
- `leadfactory/services/mockup_qa_service.py` - QA workflow logic

#### **MU-4: Concept Gallery Filter**
```gherkin
Given multiple versions exist When user selects "Show approved" filter Then only Pass concepts show
```

**Implementation Tasks:**
- [ ] Add filtering to mockup gallery
- [ ] Create status-based views
- [ ] Add filter controls to UI

#### **MU-5: Version Diff View**
```gherkin
Given v1 and v3 approved When diff icon clicked Then overlay highlights changes in concept text
```

**Implementation Tasks:**
- [ ] Implement version comparison logic
- [ ] Create diff visualization component
- [ ] Add version history tracking

**Files to Modify:**
- `leadfactory/static/dashboard.html` - Add mockup gallery
- `leadfactory/services/mockup_png_uploader.py` - Add versioning

**Estimated Time:** 3 days

---

## 🎯 **FEATURE 4: SMB Outreach Email** (90% → 95%)

### **Missing Scenarios to Implement:**

#### **EM-3: Follow-up Auto-send**
```gherkin
Given lead opened but did not reply by Day 3 When scheduler runs Then follow-up template sent automatically
```

**Implementation Tasks:**
- [ ] Create follow-up scheduler service
- [ ] Add follow-up email templates
- [ ] Implement engagement tracking logic
- [ ] Add cron job for scheduling

**Files to Create:**
- `leadfactory/services/follow_up_scheduler.py` - New service
- `leadfactory/templates/email/follow_up_day3.html` - Template
- `scripts/follow_up_cron.py` - Scheduler script

**Estimated Time:** 1 day

---

## 🎯 **FEATURE 5: Engagement Tracking** (85% → 95%)

### **Missing Scenarios to Implement:**

#### **TR-4: Bulk Qualify for Handoff**
```gherkin
Given 5 leads flagged Warm When user selects all and clicks "Qualify & Handoff" Then they move to Handoff queue
```

**Implementation Tasks:**
- [ ] Add bulk selection UI
- [ ] Create handoff queue management
- [ ] Add bulk qualify API endpoint
- [ ] Implement queue status tracking

**Files to Modify:**
- `leadfactory/static/dashboard.html` - Add bulk selection
- `leadfactory/api/engagement_api.py` - Add bulk endpoints

#### **TR-5: Webhook Failure Handling**
```gherkin
Given SendGrid webhook secret wrong When event arrives Then system logs warning and retries 3×
```

**Implementation Tasks:**
- [ ] Enhance webhook validation
- [ ] Add retry mechanism for failed webhooks
- [ ] Improve error logging
- [ ] Add webhook health monitoring

**Files to Modify:**
- `leadfactory/webhooks/sendgrid_webhook.py` - Enhance validation
- `leadfactory/monitoring/webhook_monitor.py` - New monitoring

**Estimated Time:** 2 days

---

## 🎯 **FEATURE 6: A/B Testing Framework** (90% → 95%)

### **Missing Scenarios to Implement:**

#### **AB-3: Test End Auto-report**
```gherkin
Given end date reached When p-value <0.05 Then system emails summary PDF
```

**Implementation Tasks:**
- [ ] Add experiment end detection
- [ ] Create PDF report generation
- [ ] Implement email notification system
- [ ] Add statistical significance checking

**Files to Create:**
- `leadfactory/ab_testing/report_generator.py` - PDF reports
- `leadfactory/ab_testing/notification_service.py` - Email notifications

**Estimated Time:** 1 day

---

## 🎯 **FEATURE 7: Analytics & Cost Dashboard** (95% → 98%)

### **Minor Improvements:**
- [ ] Add more detailed cost breakdown views
- [ ] Improve real-time metric updates
- [ ] Add export format options

**Estimated Time:** 0.5 days

---

## 🎯 **FEATURE 8: Fallback & Retry** (80% → 95%)

### **Missing Scenarios to Implement:**

#### **FL-3: Manual Fix Scripts**
```gherkin
Given ENV002 invalid API key When user runs fix script Then .env updated and validation passes
```

**Implementation Tasks:**
- [ ] Create fix script library
- [ ] Add script execution UI
- [ ] Implement .env file updates
- [ ] Add validation after fixes

**Files to Create:**
- `leadfactory/services/fix_script_service.py` - Script management
- `scripts/fixes/` - Fix script library

#### **FL-4: Bulk Dismiss UI**
```gherkin
Given 10 non-critical errors When user selects all & clicks "Dismiss" Then queue clears
```

**Implementation Tasks:**
- [ ] Add bulk error management UI
- [ ] Create dismiss functionality
- [ ] Add error categorization
- [ ] Implement queue management

**Files to Modify:**
- `leadfactory/static/dashboard.html` - Add error management
- `leadfactory/api/error_management_api.py` - New file

**Estimated Time:** 2 days

---

## 📅 **IMPLEMENTATION TIMELINE**

### **Week 1: Core Functionality (High Priority)**
- **Days 1-2**: Feature 1 (Lead Acquisition improvements)
- **Days 3-4**: Feature 3 (Mockup QA improvements)
- **Day 5**: Feature 2 (Scoring improvements)

### **Week 2: User Experience (Medium Priority)**
- **Days 1-2**: Feature 5 (Engagement Tracking)
- **Days 1-2**: Feature 8 (Fallback & Retry)
- **Day 3**: Feature 4 (Email Follow-ups)
- **Days 4-5**: Feature 6 (A/B Testing) + Feature 7 (Analytics)

## 🎯 **SUCCESS METRICS**

### **Target Achievement:**
- **BDD Coverage**: 77% → 95%
- **Implemented Scenarios**: 48/62 → 59/62
- **User Experience**: Complete workflow coverage
- **Production Readiness**: All core scenarios tested

### **Acceptance Criteria:**
- [ ] All new BDD tests passing
- [ ] Integration tests covering new scenarios
- [ ] UI components responsive and functional
- [ ] Error handling comprehensive
- [ ] Documentation updated

## 🚀 **DEPLOYMENT STRATEGY**

### **Phase 1: Critical Gaps (Week 1)**
Deploy improvements to Features 1-3 immediately as they impact core functionality.

### **Phase 2: UX Enhancements (Week 2)**
Deploy Features 4-8 improvements to complete the user experience.

### **Rollback Plan:**
Each feature enhancement includes feature flags for safe rollback if issues arise.

---

**Total Estimated Effort:** 12-15 development days
**Target Completion:** 2 weeks
**Final BDD Coverage:** 95%+ (59/62 scenarios)
