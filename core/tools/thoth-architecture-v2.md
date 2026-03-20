# Thoth Autonomous Agent: Complete System Architecture

**Version:** 0.2 — Post-Research Synthesis
**Date:** March 2026
**Status:** Pre-Implementation Reference

---

## 1. Core Design Philosophy

Thoth is a **constrained, semi-autonomous economic agent** running on a Jetson Orin Nano 8GB. Three non-negotiable principles:

1. **Operator experience comes first.** Daily involvement under 15–30 minutes. If it feels like a chore, the project dies.
2. **Autonomy is earned, not assumed.** Starts narrow, expands via calibration matrix as trust is established.
3. **Structure replaces intelligence.** Hardcoded constraints, classical algorithms, fixed pipelines. LLMs handle ideation and content generation — not judgment calls.

**Architectural maxim (Anthropic's own recommendation):** "LLM proposes, deterministic code executes." The agent loop is a stateless reducer: `step(state) → state`. The LLM returns structured output, Python match/case executes deterministically, state persists in SQLite.

---

## 2. Hardware & Infrastructure

### Jetson Orin Nano 8GB

- ARM64, 1024 CUDA cores, 102 GB/s memory bandwidth (MAXN SUPER mode)
- JetPack 6.2: CUDA 12.6, Ubuntu 22.04, Python 3.10
- 1TB NVMe SSD (storage, swap, model weights, backups)

### Day-One Optimizations

- Disable desktop GUI: `sudo systemctl set-default multi-user.target` → recovers ~800MB RAM
- 16GB NVMe swap: `sudo fallocate -l 16G /ssd/16GB.swap` with `swappiness=10`
- Disable nvzramconfig and unnecessary services
- Enable MAXN SUPER mode: `sudo nvpmodel -m 2` + `jetson_clocks`
- Available RAM after optimization: ~6.5–7GB

### Memory Budget

| Component | RAM | When Active |
|---|---|---|
| Ubuntu + JetPack (headless) | ~1.0 GB | Always |
| Scrapy (HTTP scraping) | 100–500 MB | During scrape cycles |
| Playwright (1 instance, JS pages) | 200–500 MB | When needed |
| FastAPI (2 uvicorn workers) | 200–400 MB | Always (serving API) |
| Caddy reverse proxy | 15–30 MB | Always |
| SQLite + Litestream | 50–200 MB | Always |
| Ollama + Qwen3.5 4B | 2–2.5 GB | During enrichment/sleep |
| Validation (Pandera + Pydantic) | ~60 MB | During pipeline runs |
| changedetection.io | ~100 MB | Always |
| Python orchestration (Thoth core) | 100–200 MB | Always |
| **Total active** | **~5–6 GB** | — |

**Key: temporal multiplexing.** Ollama's 2.5GB is only resident during enrichment. Set `OLLAMA_KEEP_ALIVE=5m` to unload when idle, freeing RAM for scraping bursts.

---

## 3. Orchestration: Custom Python, No Framework

### Why Not OpenClaw

- 7+ CVEs since January 2026, including CVSS 8.8 RCE
- 20% of ClawHub skills found to be malicious (Bitdefender)
- Node.js runtime mismatch with Python stack
- 4-5 background API calls per interaction (token-maximizing by design)
- 5,000–10,000 token system prompt overhead per call

### Architecture: 12-Factor Agent Pattern

~200–500 lines of Python. Core components:

- **Direct Anthropic API** with native `tool_use` (~80 lines for full tool calling)
- **SQLite** for state persistence and blackboard communication between agents
- **Ollama** (OpenAI-compatible endpoint) for local model inference
- **Coordinator + subagents** with isolated context windows, condensed summary returns (1,000–2,000 tokens)
- **Optional: PydanticAI** for type-safe tool definitions and structured output validation (~30–100MB overhead)

### Token Optimization Stack (targeting 80–95% savings vs. naive)

1. **Prompt caching** on every Anthropic call — 90% off cached input tokens. Break-even at 2 cache reads. System prompts, tool definitions, coordinator instructions all cached.
2. **Aggressive model routing** — 60–80% of tasks handled locally at $0. Rule-based router (no AI needed for routing decisions).
3. **Tool result summarization** — subagents return 1,000–2,000 token summaries, not full results. Full data stored in SQLite with reference pointers.
4. **Sliding window context** — last 3–5 messages in full, earlier messages summarized incrementally. 70%+ context reduction.
5. **Dynamic tool loading** — only relevant tools per call, not all 20+. Up to 98.7% reduction in tool definition tokens.
6. **Batch API** for all non-real-time LLM work — flat 50% discount.

Combined effective savings: **80–95% vs. routing everything to frontier models.**

---

## 4. Three-Tier Model Architecture

### Tier 1: Local Jetson (zero marginal cost) — 60–80% of workload

**Model:** Qwen3.5 4B (Q4_K_M quantization, ~2.5GB)
**Engine:** Ollama (native install, NOT Docker — Docker causes CPU-only fallback on Jetson)
**Speed:** 25–40 tokens/second
**Capabilities:** Classification (85–90% accuracy), data extraction, simple summarization, routing decisions, all sleep-mode tasks
**Optimization:** KV cache quantization (`--cache-type-k q8_0 --cache-type-v q4_0`) extends context 2–4x

### Tier 2: Budget Cloud ($0–0.10/MTok) — 15–25% of workload

**Primary:** Google AI Studio free tier (Gemini 2.5 Flash, 1,000 req/day, no credit card)
**Backup:** GPT-5 Nano ($0.05/$0.40/MTok) or Gemini 2.0 Flash ($0.10/$0.40/MTok)
**Use for:** Medium-complexity tasks exceeding local model capability, structured JSON extraction

### Tier 3: Frontier ($0 via subscription, or API when quota exhausted) — 10–20% of workload

**Primary:** Claude Code CLI `-p` flag (Pro subscription, ToS-compliant programmatic access)
**Backup:** Claude Haiku batch API ($0.50/$2.50/MTok with batch discount)
**Quality-critical:** Claude Sonnet batch API ($1.50/$7.50/MTok with batch discount)
**Use for:** Research synthesis, complex analysis, newsletter content generation, code generation

### Monthly Cost Estimate

| Component | Cost |
|---|---|
| Tier 1 (local) | $0 |
| Tier 2 (Google free tier) | $0 |
| Tier 3 (Claude Code via Pro sub) | $0 (within quota) |
| Tier 3 overflow (batch API) | $5–15 |
| Jetson electricity | $1–4 |
| **Total inference** | **$6–19/month** |

---

## 5. Memory Architecture

Organized by **what it's about**, not where it came from. Source tagged as metadata.

### Categories

**Domain Knowledge** — Facts about markets, platforms, APIs, regulations.
- "USAspending.gov: no auth required, POST-based search, 5,000 records/page max"
- "Apify Store commission: 20%, PPE model preferred, payout minimum $20"

**Operational Knowledge** — Learned procedures and patterns.
- "SEC EDGAR rate limit: 10 req/sec with User-Agent header required"
- "Newsletter subject lines with specific dollar amounts: +12% open rate"

**Strategic Knowledge** — Evaluated hypotheses and outcomes.
- "Government IT spending newsletter: 340 subscribers after 8 weeks, 42% open rate"
- "Auto parts price tracker: listed on Apify, 3 users in 2 weeks, insufficient traction"

**Self-Knowledge (Calibration Matrix)** — Capability assessment and self-evaluation reliability.
- "Scraping tasks: 92% success, self-assessment accuracy ±5% (reliable)"
- "Newsletter drafts: 68% human approval rate, self-score correlation 0.4 (unreliable — always flag for review)"

### Schema (SQLite)

```sql
CREATE TABLE knowledge (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,  -- domain / operational / strategic / self
    domain_tags TEXT NOT NULL,  -- JSON array, searchable
    content TEXT NOT NULL,
    source TEXT NOT NULL,  -- deep-research / self-discovered / human-provided / execution-log
    confidence REAL DEFAULT 0.5,  -- 0.0 to 1.0
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- nullable, for facts that go stale
    last_validated TIMESTAMP,
    references TEXT  -- JSON array of source links/log IDs
);

CREATE INDEX idx_knowledge_category ON knowledge(category);
CREATE INDEX idx_knowledge_tags ON knowledge(domain_tags);
CREATE INDEX idx_knowledge_expires ON knowledge(expires_at);
```

### Confidence Weighting by Source

- Deep research (Claude Max/Code): 0.8–0.9 base confidence
- Human-provided: 0.9–1.0
- Self-discovered (single observation): 0.3–0.5
- Self-discovered (confirmed across multiple observations): 0.6–0.8
- Execution log (hard data): 0.95–1.0

### Memory Maintenance (sleep-mode tasks)

- Scan for entries approaching expiration, generate validation tasks
- Detect conflicting entries, flag for resolution
- Consolidate repeated operational observations into higher-confidence entries
- Prune low-confidence entries older than 90 days with no validation

---

## 6. Daily Decision Loop

Fixed sequence. Every phase has defined scope, resource budget, completion condition. Nothing is open-ended.

### Phase 1: WAKE (Local, $0)

- Read monitoring alerts and scheduled task results from SQLite
- Pull metrics: revenue by stream, costs by category, subscribers, API health
- Check external triggers: marketplace notifications, platform messages, errors
- Check operator schedule (calendar integration) → set availability flag
- Output: structured state object

### Phase 2: ASSESS (Local, $0)

- Compare each strategy's metrics against hardcoded thresholds
- Revenue vs. cost (trailing 7-day average)
- Growth rate vs. minimum trajectory
- Error rate vs. maximum threshold
- Token spend vs. daily allocation
- Flag threshold violations
- Output: strategy health report + anomaly list

### Phase 3: PLAN (one Tier 1 or Tier 2 call)

- Load task templates for active strategies
- Query relevant memory for context
- Generate specific task list with token budgets and success criteria
- If research needs exist, generate prioritized prompts (BLOCKING / IMPORTANT / NICE-TO-HAVE)
- Output: ordered task queue + research prompt queue

### Phase 4: EXECUTE (primary cost center)

- Run tasks in priority order, each with:
  - Token budget ceiling (hard stop)
  - Timeout (hard stop)
  - Success criterion (measurable)
  - Failure handling: log diagnostic, move on (max 3 retries)
- After each task: log result, update operational memory, record token cost
- Output: execution log

### Phase 5: REPORT (one Tier 1 call for summarization)

Discord delivery, structured for 30-second scan:
- **Status line**: one sentence overall health
- **Numbers**: revenue, costs, net, subscribers (with trend arrows)
- **Completed**: one line per successful task
- **Failed**: one line per failure with diagnostic
- **Needs you**: pre-digested decisions with recommendations
- **Interesting**: surprising findings, opportunities (separate from operational)
- **Research prompts**: ranked needs with ready-to-use prompts (if any)

### Phase 6: SLEEP (Local, $0)

**"Dreams" — validation and consolidation:**
- Statistical anomaly detection on all data collected during EXECUTE
- Schema drift checks against stored baselines
- Cross-reference new data against historical patterns in memory
- Flag suspicious data for morning briefing

**Production tasks:**
- Overnight scraping with longer timeouts and more thorough validation
- Data preprocessing for next cycle
- Knowledge base maintenance (expiration, consolidation, pruning)
- X/GitHub monitoring for AI news and useful tools
- Local model experiments (prompt optimization, quality benchmarks)
- changedetection.io monitoring of scraping targets

**Sleep-mode inference:** Because speed doesn't matter overnight, can run larger quantized models (Qwen 3 8B at 10-20 t/s) for higher quality on tasks like knowledge consolidation and data analysis.

### Schedule Awareness

- Read-only access to operator's calendar
- During unavailable periods: conservative mode (no approvals acted on, no content published, spending within pre-approved limits, decisions queued)
- First available morning: catch-up summary with everything held for review

---

## 7. Research Pipeline

### Three Channels

**Automated (Claude Code `-p`):** Thoth generates prompt, calls CLI, parses JSON output, stores in memory. For routine research within Pro subscription quota. Thoth tracks estimated token usage against weekly rolling limit.

**Manual — Claude Max (via father's account):** For deep strategic research. Thoth generates prompt, presents in Discord #research-prompts channel. Human runs through Claude Max, pastes output. Thoth parses formatted output into memory.

**Manual — ChatGPT Plus (via operator):** Secondary research oracle. Useful for getting a second perspective and cross-validating findings from Claude.

### Prompt Generation Rules

- Demand-driven, not scheduled
- Prioritized: BLOCKING / IMPORTANT / NICE-TO-HAVE
- Templated for consistent output formatting
- Self-formatting: instructions for output structure that Thoth can parse directly
- Typical volume: 0–2/day automated, 0–2/day manual

### Sanitization Benefit

Claude/ChatGPT processes raw web content. Thoth receives only synthesized, structured knowledge. Eliminates prompt injection risk and reduces token waste from raw content processing.

---

## 8. Hardcoded Constraints (in code, not prompts)

### Financial

- Per-task token budget ceiling: hard stop at limit
- Daily total token budget: no new API calls after limit
- Strategy-level budget allocation: each strategy has its own pool
- Reserve budget: $40 minimum balance — never touched
- Claude Code weekly quota tracking: estimated consumption before each call
- Cost tracking: every API call logged with task attribution

### Operational

- Domain allowlist for scraping (programmatic enforcement)
- Rate limiting per domain (hardcoded delays, robots.txt compliance)
- No PII collection (programmatic check before storage)
- Retry limits: max 3 per task, then fail and log
- Constraint code is read-only to all agents
- Ollama memory management: OLLAMA_KEEP_ALIVE=5m, MAX_LOADED_MODELS=1

### Escalation

- Financial consequence > $5: human approval required
- New platform/service registration: human action required
- Content published externally: human review required (legally necessary)
- Threshold violation in ASSESS: immediate Discord notification
- 3 consecutive task failures: halt task category, escalate
- Claude Code quota approaching limit: switch to manual research pipeline

### Safety

- No execution of code from external/untrusted sources
- All generated code runs in sandboxed environment
- API credentials in encrypted credential manager, never in prompts
- Daily automated backup via Litestream to Backblaze B2
- systemd watchdog on all services (30s health check, auto-restart)

---

## 9. Revenue Strategy: Layered Portfolio

### Stream A: Federal Spending Intelligence Newsletter (Beehiiv)

**Niche:** Government contract and spending analysis
**Why this niche:** 85% automatable, structured free data (USAspending.gov, no auth), low human expertise requirement, $5,000+/year pricing gap between free data and Bloomberg Government, near-zero regulatory risk (informational, not investment advice), B2B audience with employer-funded budgets

**Data sources (all free, structured JSON, no auth or generous limits):**
- USAspending.gov API — all federal contracts, grants, loans
- Treasury Fiscal Data API — spending by category, debt metrics
- FRED API — 816,000+ economic series (120 req/min, free key)
- SAM.gov — contract opportunities (10 req/day public, 1,000/day system account)

**Weekly production cycle:**
- Mon–Wed: Automated data collection via API calls (EXECUTE phase)
- Wed–Thu: Automated analysis — spending changes, top awards, anomaly detection (EXECUTE)
- Thu: AI draft generation — structured newsletter with tables, charts, narratives (EXECUTE)
- Fri: Human review 15–30 min — add policy context, verify anomalies, editorial decisions
- Fri/Sat: Publish via Beehiiv

**Revenue model:**
- Beehiiv Boosts from day 1 (~$1.63/subscriber earned)
- Beehiiv Ad Network at 1,000+ subscribers ($100–500/month)
- Paid tier at $29–49/month (target 5% conversion)
- Direct sponsorships at 5,000+ subscribers ($500–3,000/placement)

**Target:** $2,000–3,000/month at 3,000 subscribers (12–18 months)

**Growth channels:** LinkedIn newsletter launch (auto-invite connections), Beehiiv Boost network, SEO via published issues, cross-promotion with adjacent newsletters, X threads with spending visualizations

### Stream B: Government Data Products (Apify Store → RapidAPI → Direct API)

**Products (prioritized):**
1. SEC filing NLP alerts — parse 8-K events, classify, deliver real-time alerts ($29–99/month)
2. State business filing aggregation — normalize 10–15 SOS portals, per-query pricing ($0.10–1.00/query)
3. FCC filing enrichment — zero existing commercial competitors ($19–49/month)

**Platform strategy:** Launch on Apify Store first (lowest friction, no hosting required, 20% commission). Expand to RapidAPI (largest audience, 25% commission, requires self-hosting via FastAPI on Jetson). Add direct API (zero commission) as volume grows.

**Technical stack:**
- Scrapy for HTTP-based scraping (government APIs, static pages)
- Playwright for JS-rendered pages (single instance, 30-min restart cycle)
- FastAPI behind Caddy for API serving (auto HTTPS, 500+ req/sec for cached responses)
- Pydantic v2 for record validation, Pandera for batch validation
- SQLite in WAL mode for storage (~400 writes/sec)
- Litestream for continuous replication to Backblaze B2

**Validation before building:** Follow the $200 playbook — marketplace research (week 1), landing page with sample data on Carrd (week 2, ~$30), cold traffic test (weeks 3–4, $120–150). Build only after 6%+ email signup rate or 3+ pre-sales from 10 outreach conversations.

**Target:** $500–1,500/month across products by months 12–18

### Stream C: Competitive Intelligence Monitoring (Phase 2, months 3–6)

- Deferred until Streams A and B are operational
- Uses shared infrastructure (scraping, enrichment, API serving)
- Target: 10–30 SMB clients at $49–99/month

### Shared Infrastructure

- Crawl4AI — supplementary for specific LLM-extraction tasks (not primary, memory leak issues)
- changedetection.io — monitor scraping target structure changes
- n8n (self-hosted) — workflow orchestration for complex multi-step pipelines
- Plotly/Matplotlib — chart generation for newsletter
- healthchecks.io — push-based monitoring (free tier: 20 checks)
- Slack/Discord webhooks — structured alerting

---

## 10. Reliability & Disaster Recovery

### Continuous Backup

- **Litestream** → Backblaze B2 (sub-second RPO for SQLite databases, ~$0.30/month for 50GB)
- **rclone** → encrypted B2 bucket hourly for non-database files
- 7-day WAL retention, 6-hour validation intervals

### Service Management

- systemd watchdog on all services (Type=notify, WatchdogSec=30s, Restart=always)
- Resource limits: MemoryMax=4G per service, CPUQuota=80%
- StartLimitBurst=5 with FailureAction=reboot-force (5 failures in 5 min → reboot)

### Power Protection

- UPS (APC BE425M, ~$55) → 60+ minutes runtime at Jetson's 7–25W draw
- apcupsd for graceful shutdown: stop pipeline → stop Litestream → sync → shutdown

### Disaster Recovery

- Ansible playbook for full device provisioning from scratch
- Golden system image via NVIDIA l4t_backup_restore.sh stored in B2
- Recovery times: software crash 5–30s, OS corruption 30–60min, hardware failure 2–4hr

### Health Monitoring

- jetson-stats for thermal monitoring (alert at 80°C warning, 90°C critical)
- smartctl for NVMe health (alert on Available Spare < 15%)
- healthchecks.io dead-man's-switch on all scheduled tasks
- All metrics stored in SQLite for trending

---

## 11. Calibration Phase (Week 1)

### Process

1. Thoth generates calibration tasks across capability areas
2. Attempts each, produces structured self-report (success, quality 1–10, output, cost, time)
3. Human scores ~5 min each: Did it work? Quality acceptable? Self-assessment match reality?
4. Results populate self-knowledge memory

### Task Areas to Calibrate

- API data collection (USAspending.gov, FRED, SEC EDGAR)
- Data transformation and analysis
- Newsletter draft generation
- Anomaly detection in financial data
- Code generation (FastAPI endpoints, scraper scripts)
- Summary generation (subagent → coordinator condensation)
- Self-evaluation accuracy across all above

### Autonomy Graduation

- Self-assessment correlation > 0.7: operate independently
- Correlation 0.4–0.7: operate with periodic spot-checks
- Correlation < 0.4: human approval required before finalizing

### Duration

10–15 tasks, ~5 min human evaluation each, spread over 5–7 days.

---

## 12. Operator Interface (Discord → Custom Dashboard)

### Phase 1: Discord (during calibration and early operation)

**Channels:**
- #daily-briefing — 30-second morning scan
- #decisions — pre-digested choices with recommendations
- #research-prompts — ready-to-use prompts ranked by urgency
- #interesting — findings, opportunities, AI news from X/GitHub monitoring
- #alerts — threshold violations and failures (muted unless firing)
- #metrics — auto-updated revenue, costs, subscribers, strategy health

### Phase 2: Custom Dashboard (once data is flowing)

- Build as an early Thoth project (portfolio piece, career capital)
- Real-time metrics, trend visualization, decision interface
- Can reference existing open-source agent dashboards for inspiration
- Keeps operator engaged through ongoing customization
- Highly adaptable to evolving needs

### Design Principles

- Summaries are curated, not log dumps
- Decisions pre-digested: tradeoffs explicit, recommendation included
- Interesting findings surfaced separately from operational noise
- Approval requires enough engagement to prevent rubber-stamping

---

## 13. Build Sequence (Proposed)

### Week 0: Environment Setup

- Jetson optimization (headless, swap, power mode)
- Install Ollama natively, pull Qwen3.5 4B
- Set up SQLite databases with WAL mode
- Install core Python dependencies
- Configure Litestream → Backblaze B2
- Set up systemd service templates
- Configure UPS and graceful shutdown

### Week 1: Core Orchestration + Calibration

- Build custom Python orchestration layer (coordinator + subagent pattern)
- Implement memory schema and basic CRUD operations
- Build the daily decision loop (WAKE → ASSESS → PLAN → EXECUTE → REPORT → SLEEP)
- Set up Discord bot with channel structure
- Run calibration tasks, build initial calibration matrix
- Configure Claude Code `-p` integration for automated research

### Week 2: Newsletter Pipeline

- Build USAspending.gov data collection pipeline
- Build analysis engine (spending changes, top awards, anomaly detection)
- Build newsletter draft generation with Beehiiv integration
- Set up Beehiiv account, configure Boosts
- Publish first issue

### Week 3: Data Product MVP

- Validate demand using $200 playbook (Carrd landing page, marketplace research)
- Build first data product pipeline (SEC filing alerts or SOS aggregation)
- List on Apify Store
- Set up FastAPI + Caddy for direct API serving

### Week 4+: Iterate

- Optimize based on calibration data
- Expand memory system based on research findings
- Begin building toward custom dashboard
- Add second data product if first shows traction
- Implement dream validation cycle
- Refine model routing based on observed task performance

---

## 14. Open Questions

1. Memory system implementation details (awaiting research prompt 3)
2. Claude Code CLI integration patterns and quota management (awaiting research prompt 9)
3. Specific SEC filing event types most valuable for alert product
4. Optimal Qwen3.5 4B quantization settings for Jetson (test during calibration)
5. Whether PydanticAI scaffolding is worth the overhead vs. pure custom Python
6. Community building and distribution strategy beyond LinkedIn/Beehiiv network

---

## 15. Success Metrics

### 30-Day

- Calibration matrix complete
- First newsletter published
- First data product listed on Apify Store
- Daily decision loop running reliably
- Operator involvement under 30 min/day

### 90-Day

- 200+ newsletter subscribers
- First revenue from Beehiiv Boosts
- Data product has measurable usage (>50 API calls/week)
- Memory system has 500+ entries across all categories
- Self-assessment reliability established for all major task types

### 180-Day

- 1,000+ newsletter subscribers
- $200+/month combined revenue (covering operating costs)
- Custom dashboard operational
- Second data product launched
- Thoth's operational knowledge enables meaningfully faster task execution than month 1

### 365-Day

- 3,000+ newsletter subscribers
- $500–1,500/month combined revenue
- System operates with genuine semi-autonomy (most days require <10 min attention)
- Portfolio of work demonstrates AI consulting capabilities
- Clear understanding of where autonomous agent boundaries actually are in practice

---

*This document synthesizes findings from 8 deep research analyses covering agent economics, orchestration frameworks, model routing, data pipeline engineering, newsletter niche selection, data product validation, and edge deployment. It is a pre-implementation reference, not a final specification. All assumptions should be validated during the calibration phase.*