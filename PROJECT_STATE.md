# Thoth V2 — Project State

**Last updated:** March 20, 2026
**Last session:** Initial build — concept to running system with real data

## What Thoth Is
A constrained, semi-autonomous economic agent on a Jetson Orin Nano 8GB.
Revenue strategy: government spending newsletter (Beehiiv) + data products (Apify/RapidAPI).
Architecture: custom Python orchestration, no frameworks. "LLM proposes, deterministic code executes."

## Current State
- Core orchestration layer COMPLETE and running
- Decision loop works: WAKE → ASSESS → PLAN → EXECUTE → REPORT
- Model router: local qwen3:4b + cloud claude-haiku-4-5
- Research agent PULLING REAL DATA from USAspending.gov via tools
- Newsletter agent GENERATING REAL CONTENT (Daily Financial Briefing)
- Discord reporting LIVE (bot posts to #commands)
- SQLite state tracking LIVE with cost logging
- GitHub repo: github.com/toby20frame/thoth-v2 (private)

## What Works
- Full decision cycle with real API data ($0.01 per cycle)
- Research tasks route to cloud (tools available), system tasks stay local
- USAspending.gov tool calls working (agency spending summaries)
- Newsletter draft generation from real data
- Thinking block filtering (/no_think + text extraction)
- Discord bot posts reports
- Git workflow established

## Known Issues
- Local model outputs still empty for system/data tasks (thinking tokens)
- Newsletter content uses wrong date (Dec 2024 instead of current)
- Data processing task produces empty output (no data passed to it)
- Discord listener still old OpenClaw version (not yet migrated)
- No calibration data yet
- Memory system exists but not populated
- Claude Code research pipeline not yet wired
- No sleep/dream cycle yet

## Key Architecture Decision Added This Session
- Research and newsletter agents force_cloud=True (need tools + quality)
- System and data agents stay local (save costs)
- _needs_cloud() method in coordinator controls routing

## Next Priorities
1. Improve local model outputs (increase tokens or switch model)
2. Fix newsletter date and content quality
3. Start calibration phase
4. Migrate Discord listener to new coordinator
5. Wire Claude Code research pipeline
6. Build proper newsletter pipeline with Beehiiv integration
7. Build first data product MVP
