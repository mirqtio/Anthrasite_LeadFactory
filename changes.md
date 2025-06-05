Gaps Between PRD and Implementation
Requirement / Gap	Path(s) Checked	Evidence of Non-Compliance	Effort	Suggested Task (JSON Snippet)
Filter modern sites – No filtering of sites with Lighthouse perf ≥ 90 or fully responsive (should be skipped to save costs).	bin/enrich.py (PageSpeed usage) · DB query in get_businesses_to_enrich	All leads with a website are enriched; no code drops high-performance ones. The enrichment query selects businesses with no prior features, regardless of PageSpeed metrics
GitHub
, and no check after computing performance_score
GitHub
GitHub
.	S	json\n{\n "title": "Skip Modern Sites in Lead Funnel",\n "description": "If PageSpeed Insights shows performance >= 90 and mobile responsive, mark lead as processed without email. Implement check in enrichment step to drop these leads.",\n "tags": ["pipeline", "performance", "cost-saving"],\n "estimate": "4 hours"\n}\n
City/State not saved – Business address is stored as one string, and city/state fields in DB are left NULL.	leadfactory/storage/postgres_storage.py	When creating a business record, city and state are explicitly set to None (not parsed from address)
GitHub
GitHub
. This means city and state columns remain empty, contrary to PRD spec to persist them.	S	json\n{\n "title": "Parse and Store City/State for Businesses",\n "description": "Extract city and state from business address and save to the `businesses` table instead of leaving them NULL. Update `create_business` logic to parse address into city/state fields.",\n "tags": ["data", "parsing"],\n "estimate": "2 hours"\n}\n
Raw Yelp JSON retention – Decision not implemented (whether to keep full Yelp API JSON).	leadfactory/storage/postgres_storage.py	The schema has yelp_response_json and google_response_json fields
GitHub
, but process_yelp_business/create_business never passes the API JSON (defaults to None)
GitHub
GitHub
. There is no task or config to purge or retain this JSON (open Issue #1).	M	json\n{\n "title": "Decide & Implement Yelp JSON Retention",\n "description": "Determine retention policy for raw Yelp/Google API JSON. If keeping, pass API response data into `create_business` so it's stored in `businesses.yelp_response_json`; if purging, remove these fields and any related storage to avoid PII retention.",\n "tags": ["data", "privacy"],\n "estimate": "6 hours"\n}\n
Screenshot generation (local) – No local headless browser fallback; external API required.	leadfactory/pipeline/screenshot.py	The code uses ScreenshotOne API exclusively and raises an exception if no API key
GitHub
. This conflicts with the local-stack requirement in v1.0 (should run on a Mac mini without cloud services). No Playwright/Chromium usage is present.	M	json\n{\n "title": "Implement Local Screenshot Capture",\n "description": "Add a Playwright (headless Chromium) fallback to capture full-page screenshots when `SCREENSHOT_ONE_KEY` is not provided, so the system can run fully on local hardware without external screenshot APIs.",\n "tags": ["screenshot", "headless", "local"],\n "estimate": "8 hours"\n}\n
Email thumbnail missing – Emails don’t embed the site screenshot thumbnail as specified.	leadfactory/pipeline/unified_gpt4o.py (email HTML) · etc/email_template.html	The generated email HTML has no <img> tag for a thumbnail
GitHub
. The template email_template.html even allocates a .mockup-container for an image
GitHub
, but the current personalization flow doesn’t populate or include the screenshot URL at send time.	M	json\n{\n "title": "Embed Website Thumbnail in Email",\n "description": "Modify email content generation to include the screenshot thumbnail. Use the stored screenshot asset (embed as inline image or via public link) in the email HTML as a small preview of the site, per PRD.",\n "tags": ["email", "thumbnail", "HTML"],\n "estimate": "4 hours"\n}\n
No scoring gate for GPT – Leads are personalized regardless of “outdated” score threshold (should require score ≥ 7/10).	leadfactory/pipeline/score.py · Email selection query	There is no logic to restrict which leads get a GPT-personalized email based on score. The query for email sending doesn’t filter by any score field (it even selects a dummy 0 as score)
GitHub
. This suggests every scraped lead with an email could get an email, violating the “score_outdated ≥ 7 triggers GPT” rule.	M	json\n{\n "title": "Apply Outdatedness Score Threshold",\n "description": "After scoring leads, only queue personalization/email for those above the outdatedness threshold (e.g. score >= 70%). Implement filtering (e.g., mark others as processed=TRUE without email) and adjust email query to exclude low-score leads.",\n "tags": ["scoring", "personalization"],\n "estimate": "6 hours"\n}\n
Email content vs. template – Custom GPT email HTML bypasses standard template (CAN-SPAM footer, unsubscribe link, etc.).	leadfactory/pipeline/unified_gpt4o.py (mock response) · etc/email_template.html	The GPT-generated email (full_email_html) is assembled manually
GitHub
GitHub
, and although a template file exists with unsubscribe link and address
GitHub
, the current flow doesn’t merge the AI content into that template. This risks missing compliance footer or styling.	M	json\n{\n "title": "Integrate AI Content with Email Template",\n "description": "Use the Jinja EmailTemplateEngine to inject GPT-generated text (subject, intro, issues list, etc.) into the predefined HTML template that includes our CAN-SPAM compliant footer and unsubscribe link. Ensure the final sent email uses the unified template.",\n "tags": ["email", "template", "compliance"],\n "estimate": "8 hours"\n}\n
Bounce rate handling – No automation to monitor bounce > 2% or warm-up a new IP pool.	Codebase-wide (SendGrid config/monitoring)	While the system records bounce events and updates status
GitHub
GitHub
, there is no code that computes bounce rate percentages or switches the SendGrid IP pool config. The PRD’s task (#21) for IP warm-up is not implemented.	M	json\n{\n "title": "Auto-Monitor Bounce Rate & IP Warmup",\n "description": "Implement a periodic check on the email_events table for bounce rate (bounces/emails sent). If >2%, log alert and switch `SENDGRID_IP_POOL` from 'shared' to 'dedicated' (or trigger IP warm-up workflow). Include unit test with fake bounce data.",\n "tags": ["deliverability", "monitoring"],\n "estimate": "6 hours"\n}\n
Audit PDF content – The delivered PDF is a placeholder, not a branded, metrics-driven audit report.	leadfactory/services/payment_service.py	The current _generate_audit_pdf writes dummy text (“placeholder audit report…”)
GitHub
 and static section headers. It does not use GPT or the actual website metrics to produce the analysis and redesign suggestions promised in the PRD.	L	json\n{\n "title": "Generate Real Audit PDF Content",\n "description": "Replace placeholder PDF generation with a comprehensive audit report. Use stored metrics (Core Web Vitals, tech stack, SEMrush data) and GPT-4 to generate an executive summary and 2-3 key findings with recommendations. Utilize the existing pdf_generator module or WeasyPrint to format a branded PDF.",\n "tags": ["report", "PDF", "GPT-4"],\n "estimate": "16 hours"\n}\n
Report link expiry – Customers only get 72 hours to download reports instead of 30 days.	leadfactory/services/payment_service.py	The Supabase link expiry is hardcoded to 72 hours (3 days)
GitHub
 when uploading the PDF. This is far shorter than the 30-day access promised.	S	json\n{\n "title": "Extend Report Link Expiry to 30 Days",\n "description": "Increase the `expiry_hours` for audit report links from 72 to 720 (30 days) when calling ReportDeliveryService.upload_and_deliver_report, to match the offering in the PRD.",\n "tags": ["report", "config"],\n "estimate": "1 hour"\n}\n
Local PDF hosting option – No alternative to Supabase for report storage on local stack.	leadfactory/services/report_delivery.py	The report delivery service uses Supabase cloud storage by default
GitHub
. There is no config to keep PDFs local (e.g. serving from the Mac mini or attaching to email) despite the v1.0 constraint to run fully on local hardware if needed.	M	json\n{\n "title": "Support Local PDF Delivery",\n "description": "Add a configuration to optionally skip Supabase upload and instead either attach the PDF to the report email or serve it via a local HTTP link. This ensures audit reports can be delivered without cloud storage when running on a local stack.",\n "tags": ["report", "local"],\n "estimate": "8 hours"\n}\n
Cost cap by service – Budget gating isn’t granular by LLM or SEMrush daily spend.	bin/budget_gate.py · .env.example	The code implements a global budget gate (enabled/threshold)
GitHub
 but does not check individual API budgets. There are no MAX_DOLLARS_LLM or MAX_DOLLARS_SEMRUSH settings (not present in .env.example
GitHub
GitHub
), so the system won’t halt if one service exceeds its daily allowance.	M	json\n{\n "title": "Enforce Per-Service Daily Cost Caps",\n "description": "Extend cost_tracking to enforce daily spend limits for LLM and SEMrush. Introduce env vars (e.g. MAX_DOLLARS_LLM, MAX_DOLLARS_SEMRUSH); when cost_tracker tallies exceed these, disable or delay those API calls for the day and log alerts.",\n "tags": ["cost", "monitoring"],\n "estimate": "6 hours"\n}\n
No DB backup – Nightly process lacks the pg_dump and off-site backup step.	scripts/run_nightly.sh	The nightly script covers lead processing and metrics but does not perform any DB dump or rsync. There is no mention of backups in code (e.g. no pg_dump call) and thus no assurance of “no single log-file loss” or database backup to an off-site NAS as required.	S	json\n{\n "title": "Implement Nightly DB Backup",\n "description": "At end of nightly.sh, add steps to dump the PostgreSQL database to local storage and rsync/SCP it to the off-site NAS. Ensure this runs after pipeline success and logs success/failure. Test by verifying a backup file appears in the expected NAS location.",\n "tags": ["ops", "backup"],\n "estimate": "3 hours"\n}\n

Proposed Task List (Order of Implementation)
Skip Modern Sites in Lead Funnel – Implement PageSpeed check to drop leads with high performance scores
GitHub
GitHub
. ([pipeline/performance])
Parse and Store City/State for Businesses – Extract city/state from address before calling create_business
GitHub
. ([data model])
Decide & Implement Yelp JSON Retention – Either save API JSON to DB or remove those fields, per privacy decision. ([data retention])
Implement Local Screenshot Capture – Add Playwright fallback when SCREENSHOT_ONE_KEY is not set
GitHub
. ([infrastructure])
Embed Website Thumbnail in Email – Include screenshot image in outbound email HTML (update template to use asset URL or inline image)
GitHub
. ([UX])
Apply Outdatedness Score Threshold – After scoring, only enqueue personalization for leads above threshold (e.g. score ≥ 70). Skip emailing low-score leads
GitHub
. ([pipeline/scoring])
Integrate AI Content with Email Template – Use Jinja template for emails so GPT text merges with CAN-SPAM footer (unsubscribe, address)
GitHub
. ([email/compliance])
Auto-Monitor Bounce Rate & IP Warmup – Cron job or hook to calculate bounce % from email_events and switch SendGrid IP pool if >2%
GitHub
. ([deliverability])
Generate Real Audit PDF Content – Use metrics and GPT-4 to produce a real audit report PDF (replace placeholder text
GitHub
 with actual findings). ([reporting])
Extend Report Link Expiry to 30 Days – Change Supabase link TTL from 72h to 720h in report delivery
GitHub
. ([config])
Support Local PDF Delivery – Provide option to attach PDFs to emails or serve locally instead of Supabase
GitHub
. ([infra/feature-flag])
Enforce Per-Service Daily Cost Caps – Update cost_tracker to stop LLM or SEMrush calls once daily spend exceeds set limits (add MAX_DOLLARS_LLM/SEMRUSH). ([cost-control])
Implement Nightly DB Backup – Append pg_dump and off-site sync to nightly script (ensure backup files are created). ([ops])
