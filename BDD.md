Below is an exhaustive, user-focused catalogue of **every feature that exists (or must exist) in Anthrasite Lead Factory v1.0**, the functions expected inside each feature, and the complete set of BDD-style usage scenarios.
At the end you’ll find a **flattened master list of all scenarios** and a short note on **UI elements that appear in the architecture but are not exercised in Phase 0**.

---

## 1  Feature Map

| #  | Feature (Phase 0 scope unless noted)                    | Purpose                                                                                   | Key References                                            |
| -- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| 1  | **Lead Acquisition & Enrichment**                       | Pull raw SMB data from Yelp & Google, enrich with external signals                        | “Lead Acquisition/Enrich (BDH + APIs)”                    |
| 2  | **Website / GBP Analysis & Scoring Engine**             | Calculate health scores from PageSpeed, SEMrush, BrightLocal, plus AI-assisted GBP review |                                                           |
| 3  | **Visual Mockup Generation & QA**                       | Produce AI redesign concept and verify quality                                            |                                                           |
| 4  | **SMB Outreach (Email)**                                | Personalised email creation, A/B test orchestration, send & follow-ups                    |                                                           |
| 5  | **Engagement Tracking & Qualification**                 | Monitor opens/clicks/replies, score intent, mark hand-off ready                           | “Define SMB Engagement Funnel”                            |
| 6  | **Agency Handoff**                                      | Match warm SMBs to agencies, transmit lead package, log status                            |                                                           |
| 7  | **Agency Feedback Collection**                          | Gather quality & commercial value ratings via form & calls                                |                                                           |
| 8  | **A/B Testing Framework (Email layer)**                 | Randomise control vs mockup groups, measure uplift                                        | “A/B Testing (Email)”                                     |
| 9  | **Analytics & Cost Dashboard**                          | Consolidate funnel KPIs, cost per lead, test results                                      | success-metric tasks                                      |
| 10 | **Fallback & Retry Workflow**                           | Standardised error handling for email-finding, AI checks, mockup QA                       | “Fallback Procedures (Task 18)”                           |
| 11 | **Pre-flight Environment Validation**                   | One-click check for API keys, .env variables, Airtable schema                             | linked to ENV00x failure patterns in code (implicit spec) |
| 12 | **Configuration & Pipeline Control UI**                 | Select vertical, zips, batch size, model choice, run/stop pipeline                        |                                                           |
| 13 | **API Key & Credential Vault**                          | CRUD for third-party tokens (Yelp, ScreenshotOne, SendGrid…)                              |                                                           |
| 14 | **Permissions & Audit Logging**                         | User roles, immutable logs of pipeline events (local log + Airtable)                      |                                                           |
| 15 | **Landing Page & LinkedIn Presence (supporting asset)** | Informational web presence; not an interactive app surface                                |                                                           |

---

## 2  Detailed Functional Decomposition & BDD Scenarios

### 1 Lead Acquisition & Enrichment

#### Functions

1. **Target Criteria Entry** – choose vertical(s), ZIP(s), batch size
2. **API Key Manager (Yelp & Google)** – validate & store tokens
3. **Acquire Leads** – call Yelp Fusion, then Google Places for enrichment
4. **Conflict-Aware Deduplication** – merge by website/phone/address+name&#x20;
5. **Email Finder Invocation** – Hunter.io lookup + fallback rule&#x20;
6. **Raw JSON Archival** – store source payloads for audit
7. **Preview Grid & Bulk Actions** – review, accept/reject, export CSV

#### BDD Usage Scenarios

| ID                         | Scenario (abbrev)                                                                                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **LA-1** Successful pull   | **Given** valid API keys & selected HVAC/10002 **When** “Acquire” is clicked **Then** 50 new leads appear with status *New* and raw JSON saved         |
| **LA-2** Missing Yelp key  | Given Yelp key is blank When “Acquire” clicked Then system blocks action and shows ENV001 guidance                                                     |
| **LA-3** Duplicate website | Given a business with same URL already exists When new batch runs Then record is merged and source list shows “yelp,google”                            |
| **LA-4** Hunter soft fail  | Given Hunter returns no email When fallback rule triggers Then lead status “Email-Missing” and pipeline skips outreach                                 |
| **LA-5** Manual reject     | Given lead list contains irrelevant business When user ticks checkbox & presses “Reject selected” Then record is archived and hidden from default view |

---

### 2 Website / GBP Analysis & Scoring Engine

#### Functions

1. **PageSpeed & SEMrush Fetch** – REST calls, store scores
2. **BrightLocal Citation Check**
3. **ScreenshotOne GBP Capture** – obtain public listing image&#x20;
4. **AI-Driven GBP Check** – GPT-4o prompt → structured JSON result&#x20;
5. **Composite Score Calculator** – weighted formula, configurable
6. **Scorecard View** – colour-coded table & drill-down modal

#### BDD Scenarios

| ID                                           | Scenario                                                                                                               |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **AN-1** Score success                       | Given valid API quotas When “Run Analysis” Then PageSpeed+SEMrush+BrightLocal scores saved and composite score visible |
| **AN-2** GBP screenshot fail, retry succeeds | Given first ScreenshotOne call times out When auto-retry runs Then image saved and AI check continues                  |
| **AN-3** AI JSON malformed                   | Given LLM returns invalid JSON When parser errors Then fallback path marks “AI-Uncertain” and score weight set to 0    |
| **AN-4** User re-weights formula             | Given admin edits weight for PageSpeed from 0.2→0.3 When changes saved Then composite scores recalc instantly          |
| **AN-5** Scorecard export                    | Given filtered view showed 30 leads When user clicks “Export scorecard CSV” Then file downloads with same filter set   |

---

### 3 Visual Mockup Generation & QA

#### Functions

1. **Website Screenshot Capture** – homepage screenshot
2. **LLM Prompt Assembly** – combine screenshot + scores into prompt
3. **Mockup Concept Generation (GPT-4o)** – returns JSON block
4. **Parallel Human/AI QA** – AI first, human override option&#x20;
5. **Mockup Status Tracker** – Pass / Needs-Revision / Fail
6. **Mockup Gallery View** – side-by-side original vs concept

#### BDD Scenarios

| ID                              | Scenario                                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **MU-1** Happy path             | Given lead has screenshot & scores When “Generate mockup” Then concept JSON stored and status “QA-Pending” |
| **MU-2** AI QA pass             | Given AI QA score ≥8/10 When auto-QA runs Then status “Approved” and outreach template embeds concept      |
| **MU-3** AI QA fail → human fix | Given AI QA score <5 When human opens QA modal and revises prompt Then regenerated concept re-evaluated    |
| **MU-4** Concept gallery filter | Given multiple versions exist When user selects “Show approved” filter Then only Pass concepts show        |
| **MU-5** Version diff view      | Given v1 and v3 approved When diff icon clicked Then overlay highlights changes in concept text            |

---

### 4 SMB Outreach (Email)

#### Functions

1. **Template Editor** – Liquid-style merge tags (business\_name, score, concept\_snippet)
2. **A/B Group Randomiser** – assign “Control” vs “Mockup” group&#x20;
3. **SendGrid Integration** – schedule & send, append UTM for CTA tracking
4. **Follow-up Sequencer** – Day +3, +7 emails configurable
5. **Outbox Monitor** – real-time status per lead (Sent, Opened, Clicked, Replied)

#### BDD Scenarios

| ID                           | Scenario                                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **EM-1** Send batch          | Given 20 approved leads When user clicks “Send emails” Then SendGrid sends 20 msgs and status becomes “Sent”  |
| **EM-2** A/B allocation      | Given test ratio 50% When batch created Then 10 leads marked A, 10 marked B and email body reflects group     |
| **EM-3** Follow-up auto-send | Given lead opened but did not reply by Day 3 When scheduler runs Then follow-up template sent automatically   |
| **EM-4** CTA click captured  | Given recipient clicks insight link When webhook received Then lead status updates to “Clicked”               |
| **EM-5** Manual pause        | Given deliverability dip detected When user toggles “Pause sending” Then queue halts and warning banner shown |

---

### 5 Engagement Tracking & Qualification

#### Functions

1. **Realtime Metrics Ingest** – parse SendGrid events
2. **Qualification Rules Engine** – escalate to “Warm” if Click OR positive reply
3. **Lead Timeline View** – chronological activity log
4. **Manual Intent Tagger** – override classification
5. **Bulk Qualify for Handoff** – multi-select warm leads → handoff queue

#### BDD Scenarios

| ID                            | Scenario                                                                                                        |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **TR-1** Auto warm            | Given lead has “Clicked” event When rule engine runs Then intent = “Warm” and handoff icon appears              |
| **TR-2** Manual override cold | Given spam reply detected When user sets “Disqualified” Then lead removed from funnel metrics                   |
| **TR-3** Timeline drill-down  | Given lead selected When user opens timeline Then all events with timestamps display                            |
| **TR-4** Bulk qualify         | Given 5 leads flagged Warm When user selects all and clicks “Qualify & Handoff” Then they move to Handoff queue |
| **TR-5** Webhook failure      | Given SendGrid webhook secret wrong When event arrives Then system logs warning and retries 3×                  |

---

### 6 Agency Handoff

#### Functions

1. **Agency Matching Engine** – rule-based (geo + capacity)
2. **Warm Intro Email** – templated message + lead package attachment&#x20;
3. **Secure Data Share Link** – time-boxed link to Airtable row / PDF
4. **Handoff Status Tracker** – “Pending”, “Accepted”, “Declined”
5. **Escalation Path** – reassign if Declined or no response 48 h

#### BDD Scenarios

| ID                              | Scenario                                                                                               |
| ------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **HA-1** Auto handoff           | Given agency capacity is open When lead qualifies Then intro email is sent and status “Pending-Agency” |
| **HA-2** Agency accepts         | Given agency clicks “Accept lead” link When webhook fires Then status “Accepted” and KPIs update       |
| **HA-3** No response → reassign | Given 48 h passed with no action When cron job runs Then lead reassigned to next agency                |
| **HA-4** Manual handoff         | Given founder selects specific agency in UI When “Send now” pressed Then same flow as auto handoff     |
| **HA-5** Decline reason logged  | Given agency declines and fills reason When submitted Then reason saved to Analytics DB                |

---

### 7 Agency Feedback Collection

#### Functions

1. **Automated Survey Email** – send Google Form link 7 days post-handoff&#x20;
2. **Call Scheduler** – Calendly-like link for follow-up call
3. **Feedback Dashboard** – rating distribution, qualitative quotes
4. **Lead-to-Revenue Attribution** – optional numeric input for closed deals

#### BDD Scenarios

| ID                                | Scenario                                                                                        |
| --------------------------------- | ----------------------------------------------------------------------------------------------- |
| **FB-1** Survey send              | Given lead status “Accepted” for 7 days When survey cron runs Then feedback email sent          |
| **FB-2** Form submission captured | Given agency submits rating 4/5 When webhook fires Then dashboard updates                       |
| **FB-3** Call booked              | Given agency clicks schedule link When slot selected Then meeting appears in founder’s calendar |
| **FB-4** Low rating alert         | Given rating ≤2 When stored Then Slack alert triggers for founder review                        |
| **FB-5** Revenue entry            | Given agency closed deal \$9k When user inputs value Then ROI metric recalculates               |

---

### 8 A/B Testing Framework

*(lives inside Email module but exposed separately for analytics)*

#### Functions

1. **Group Assignment Service** – seedable RNG, respects batch size
2. **Metric Collector** – per-group engagement, warm rate, cost
3. **Stat-Sig Calculator** – χ² or z-test if N≥30
4. **Experiment Dashboard** – uplift %, p-value, winner highlight

#### BDD Scenarios

| ID                                 | Scenario                                                                                                      |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **AB-1** Create experiment         | Given template “Mockup Impact” exists When user enables A/B Then control & variant defined                    |
| **AB-2** Real-time stats           | Given 100 emails sent When 30 events processed Then dashboard shows interim uplift                            |
| **AB-3** Test end auto-report      | Given end date reached When p-value <0.05 Then system emails summary PDF                                      |
| **AB-4** Insufficient sample       | Given total warm leads <30 When period ends Then system labels result “Inconclusive”                          |
| **AB-5** Change allocation mid-run | Given experiment active When user edits ratio 50→70% Then warning modal appears and change applies next batch |

---

### 9 Analytics & Cost Dashboard

#### Functions

1. **Funnel KPI Tiles** – Sent→Warm→Accepted conversion
2. **Cost per Stage Graph** – stacked cost components vs target&#x20;
3. **Model / Prompt Performance Table** – latency, cost, QA pass-rate
4. **Drill-down Filters** – by vertical, geo, date range
5. **Export PDF / CSV** – share report with investors

#### BDD Scenarios

| ID                           | Scenario                                                                              |
| ---------------------------- | ------------------------------------------------------------------------------------- |
| **ANL-1** View KPIs          | Given data loaded When user opens Dashboard Then tiles show latest numbers            |
| **ANL-2** Cost target breach | Given CPL >\$50 When threshold crossed Then tile turns red and email alert sent       |
| **ANL-3** Model comparison   | Given multiple LLM configs When user selects “Prompt v2” Then table refreshes metrics |
| **ANL-4** Filter by geo      | Given 3 metros When “NYC” selected Then charts update accordingly                     |
| **ANL-5** Export report      | Given CFO role When “Download PDF” clicked Then branded report downloads              |

---

### 10 Fallback & Retry Workflow

#### Functions

1. **Central Error Registry** – ENV00x patterns, AI-error classes
2. **Retry Scheduler** – exponential backoff, max 3 attempts
3. **Manual Resolution Queue** – surface un-auto-resolvable failures
4. **Resolution Script Runner** – one-click run predefined fix script

#### BDD Scenarios

| ID                             | Scenario                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| **FL-1** Auto retry email-find | Given Hunter returns 500 When scheduler runs Then 2nd attempt succeeds                         |
| **FL-2** Exhausted retries     | Given all 3 screenshot attempts fail When max reached Then lead flagged “Needs human”          |
| **FL-3** Manual fix env var    | Given ENV002 invalid API key When user runs fix script Then .env updated and validation passes |
| **FL-4** Bulk dismiss          | Given 10 non-critical errors When user selects all & clicks “Dismiss” Then queue clears        |
| **FL-5** Error metrics         | Given errors logged When dashboard opened Then bar chart shows error counts by type            |

---

### 11 – 15 (Operational & Support Features)

For brevity, only unique user interactions are listed; they follow same Given/When/Then pattern:

| Feature                                 | Representative Scenarios (IDs)                                                                                                              |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Pre-flight Validation**               | **PF-1** Missing variable blocks run; **PF-2** CLI flag `--skip-check` allowed only for admin; **PF-3** Success prints green “READY” banner |
| **Configuration & Pipeline Control UI** | **PC-1** Start run with “dry-run”; **PC-2** Edit batch size live; **PC-3** Cancel running job safely                                        |
| **API Credential Vault**                | **CR-1** Add key with expiry reminder; **CR-2** Rotate SendGrid key and auto-update .env                                                    |
| **Permissions & Audit Logs**            | **AU-1** Viewer role cannot send emails; **AU-2** Every state change recorded with timestamp                                                |
| **Landing Page / LinkedIn**             | **LP-1** Update headline copy; **LP-2** Track click-throughs from page to insight link                                                      |

---

## 3  Flattened Master Scenario List

```
LA-1, LA-2, LA-3, LA-4, LA-5,
AN-1, AN-2, AN-3, AN-4, AN-5,
MU-1, MU-2, MU-3, MU-4, MU-5,
EM-1, EM-2, EM-3, EM-4, EM-5,
TR-1, TR-2, TR-3, TR-4, TR-5,
HA-1, HA-2, HA-3, HA-4, HA-5,
FB-1, FB-2, FB-3, FB-4, FB-5,
AB-1, AB-2, AB-3, AB-4, AB-5,
ANL-1, ANL-2, ANL-3, ANL-4, ANL-5,
FL-1, FL-2, FL-3, FL-4, FL-5,
PF-1, PF-2, PF-3,
PC-1, PC-2, PC-3,
CR-1, CR-2,
AU-1, AU-2,
LP-1, LP-2
```

*(62 total discrete behavioural scenarios.)*

---

## 4  UI Elements Not Exercised in Phase 0

The high-level architecture shows additional marketplace components that **exist in the long-term vision but have no interactive surfaces in Phase 0**, so they should be hidden or clearly disabled to avoid user confusion:

* **Self-Serve SMB Portal** – Digital scorecard, service discovery, booking, payment&#x20;
* **Provider Profiles & Reviews, Project Management Chat, Scheduling, Payment Processing** – all on the marketplace side&#x20;
* **Advanced Analytics / Data-Monetisation dashboards beyond basic funnel & cost metrics** – flagged in diagram but not built&#x20;

Making these inert or “coming soon” mitigates dead-end clicks and scope creep during Phase 0 validation.

---

This blueprint should give design, engineering, QA, and stakeholders a **shared, test-able understanding** of every expected interaction in Anthrasite Lead Factory v1.0.
