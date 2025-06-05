Below is a **fully-specified Product-Requirements Document (PRD)** for **Anthrasite Lead Factory v1.0** that reflects the *audit-first* pivot, local-stack launch constraints, and the most recent funnel / cost assumptions.
After the PRD you’ll find a **“Deep-Research” analysis prompt** you can paste into GPT-4o (or any code-aware model) to compare these requirements against the repo at `mirqtio/Anthrasite_LeadFactory` and surface implementation gaps.

---

# Product Requirements Document

### Anthrasite Lead Factory v1.0 (Local-stack)

| Field                 | Detail                                                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Status**            | Draft 1.0 – updated after audit-first pivot                                                                         |
| **Doc owner**         | CEO / Founder                                                                                                       |
| **Stakeholders**      | COO (ops & finance) · CPO (growth & UX) · CTO (infra & code)                                                        |
| **Target release**    | **T + 6 weeks** from doc sign-off (see timeline §10)                                                                |
| **Success criterion** | ≥ 0.25 % paid-audit conversion on 40 k emails/day while variable cost ≤ \$0.016 / email and inbox placement ≥ 90 %. |

---

## 1 Overview

Lead Factory is an automated pipeline that **discovers SMB websites, diagnoses “outdatedness”, generates personalised audit offers, processes payment, and delivers a branded PDF report**—all without human intervention.
Phase-one runs entirely on a single Mac mini (M4, 24 GB) to keep burn under \$10 k until traction is proven; cloud migration gates on cash-flow milestones.

> **Why now?**
> *Claude Opus 4* and *Gemini 2.5 Pro* can draft on-brand copy + redesign suggestions in one shot, letting us “show value before we charge”. 60 % + of US SMB sites fail Core Web Vitals and are largely invisible outside major metros.

---

## 2 User personas & value

| Persona                                            | Pain today                                               | Value we deliver                                                                         |
| -------------------------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **SMB Owner** (Main-Street plumber, florist, etc.) | Outdated site; no idea what to fix; hates sales calls.   | One-page email with thumbnail, *3 actionable fixes*, \$100 deep-dive PDF, no commitment. |
| **Agency AE** (future phase)                       | Churny lead lists; time wasted on unqualified prospects. | Lead has already paid \$100 and *asks* for help; audit PDF ≤7 days old.                  |

---

## 3 Goals & success metrics

| Goal             | Metric                               |                                 Target |
| ---------------- | ------------------------------------ | -------------------------------------: |
| Grow paid audits | Audit purchases / emails sent        | **0.25 %** (bleak) → 0.40 % (moderate) |
| Keep CAC low     | Variable cost / email                |                          **≤ \$0.016** |
| Deliver reliably | Inbox placement                      |            ≥ 90 % (GlockApps seed-box) |
| Prove cash-flow  | EBITDA positive                      |   By end of Month 1 at 20 k emails/day |
| Validate roadmap | Agency-lead opt-in from audit buyers |                        15 % by Month 4 |

---

## 4 Functional requirements

### 4.1 Data acquisition

1. **Scrape SMB URLs**

   * Call Yelp Fusion API (`/businesses/search`) at ≤4 500 calls/day.
   * Harvest ≤50 listings per call ⇒ up to 225 k SMB URLs/day.
   * Persist to `businesses(url, name, city, state, yelp_id, scraped_at)`.

2. **Rule-out obviously modern sites**

   * For each URL run Google PageSpeed Insights (mobile) – free tier.
   * Filter out `lighthouse_performance ≥ 90` **and** `is_responsive = true`.

3. **SEO / tech-stack check**

   * Batch 50 URLs → SEMrush ‘Bulk Metrics’ (Guru).
   * Flag `old_CMS`, `missing_schema`, `DA < 20`.

4. **Local HTML fetch**

   * Headless Chromium (Playwright) renders page; Core Web Vitals JS.
   * Save critical CSS/JS signals to `technology_score`.

5. **Screenshot generation**

   * Local Chrome full-height PNG (≈400 kB).
   * Path stored in `screenshots/`.

### 4.2 Scoring & personalisation

1. **Scoring engine** (already implemented YAML rule system).
2. **Threshold to personalise** – `score_outdated ≥ 7/10` triggers GPT.
3. **GPT-4o multimodal call**

   * Input: screenshot + 5 meta-features + vertical keyword.
   * Output JSON:

     ```json
     { "subject": "...", "intro": "...", "three_issues": ["..."], "impact": "...", "thumbnail": "<base64>" }
     ```
4. **Email assembly**

   * HTML template with embedded thumbnail.
   * CAN-SPAM footer + one-click unsubscribe.

### 4.3 Email delivery

* SendGrid **Essentials** shared IP for <40 k/day.
* Track events → `sendgrid_events` table (opens, clicks, bounces, spam).
* Hard bounce > 2 % triggers IP warm-up pool task (#21).

### 4.4 Payment & report

1. Stripe **Checkout** link (Product: “Website Audit”, \$100, one-time).

2. Webhook `payment_intent.succeeded`

   * Marks row as `paid_at`.
   * Queues `report_task`.

3. **Report generation**

   * GPT-4o generates header & narrative using saved metrics.
   * WeasyPrint HTML→PDF (`reports/{business_id}.pdf`).
   * Email with download link + 30-day hosted URL.

### 4.5 Back-office & ops

* Daily cost cap enforcement (`MAX_DOLLARS_LLM`, `MAX_DOLLARS_SEMRUSH`).
* Prometheus metrics & Grafana alarms (CPU > 90 %, 429 errors, GPT spend).
* Nightly `pg_dump` to attached SSD and rsync to off-site NAS.

---

## 5 Non-functional

| Attribute       | Requirement                                                                              |
| --------------- | ---------------------------------------------------------------------------------------- |
| **Perf**        | End-to-end (scrape→email) ≤ 4 h for 20 k URLs on Mac mini.                               |
| **Reliability** | MTTR ≤ 5 min (watchdog restarts); no single log-file loss.                               |
| **Scalability** | Code container-ready; config toggle to move scraper & DAG to AWS Fargate at 10 × volume. |
| **Security**    | API keys in 1Password; Stripe keys rotated 90 d; macOS FW on.                            |
| **Compliance**  | CAN-SPAM footer, unsubscribe DB, privacy policy link.                                    |

---

## 6 Out-of-scope for v1.0

* Agency referral flow (still spec-ed, but disabled by feature flag).
* GPU auto-provision (Task 22).
* Advanced analytics dashboard (Task 12).
* Dedicated SendGrid IP pool (won’t be bought until bounce >2 %).

---

## 7 Open issues / decisions

| # | Issue                                             | Owner       | Deadline              |
| - | ------------------------------------------------- | ----------- | --------------------- |
| 1 | Keep/Purge raw Yelp JSON after metrics extracted? | COO + Legal | End of sprint-1       |
| 2 | Refund guarantee wording (double money-back?)     | CPO         | Before first send     |
| 3 | Local vs S3 bucket for PDF hosting                | CTO         | When first audit sold |
| 4 | What counts as “reasonable salary” for founder?   | CFO advisor | Pre-tax filing        |

---

## 8 Metrics & instrumentation

* **event\_email\_sent**, **event\_email\_open**, **event\_audit\_paid**, **event\_refund**, tagged with `variant_id` for A/B.
* Grafana panels: cost-per-email (last 24 h), cumulative profit, GPT token usage, Yelp 429 count.

---

## 9 Risks & mitigations

| Risk                                 | Likelihood | Impact               | Mitigation                                           |
| ------------------------------------ | ---------- | -------------------- | ---------------------------------------------------- |
| Yelp throttles below 4 500 calls/day | Med        | starves funnel       | Exponential back-off + Google Places paid tier ready |
| Shared IP hits spam traps            | Med        | kills deliverability | GlockApps testing; quick-swap to dedicated pool      |
| Stripe disputes >1 %                 | Low        | account review       | Clear refund link; friendly email tone               |
| Mac mini hardware failure            | Low        | full stop            | Weekly bootable clone + cheap cold spare on shelf    |

---

## 10 Timeline (assuming code base ≈90 % complete)

| Week  | Milestone                                                  |
| ----- | ---------------------------------------------------------- |
| **0** | Tag `pre-launch` branch; PRD sign-off.                     |
| 1     | Deploy services on Mac; domain & email auth live.          |
| 2     | Smoke-test 1 000 emails; Stripe live mode.                 |
| 3     | Batch 5 000 emails; cut KPI baseline.                      |
| 4     | Raise to 20 k emails/day; cost monitoring green.           |
| 6     | Evidence gate met → turn on SEMrush Guru + tier-1 scaling. |

---

# Deep-Research Prompt for GPT Code Audit

> **System**: “You are a code-analysis assistant with deep knowledge of Python, SQL, Docker, and CI. Read the following PRD and compare it to the repository `mirqtio/Anthrasite_LeadFactory` (assume `main` branch). Identify every requirement that is **missing, partially implemented, or stale**. For each gap give:
>
> * path(s) you checked,
> * evidence of non-compliance (lines, functions, TODOs),
> * effort estimate (S/M/L),
> * suggested task-master task JSON snippet.
>
> Return Markdown with a table of gaps followed by an ordered list of tasks.

*(Paste the PRD above as the “context” block, then run the prompt in GPT-4o or Claude Opus from the repo root with a tool like [Code Interpreter](https://github.com/features/copilot). The model will traverse the tree, diff vs spec, and spit back a ready-to-import task list.)*
