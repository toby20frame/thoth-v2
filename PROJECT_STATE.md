# Thoth V2 — Project State

**Last updated:** March 20, 2026
**Last session:** Initial build — concept to working system in one conversation

## What Thoth Is
A constrained, semi-autonomous economic agent on a Jetson Orin Nano 8GB.
Revenue strategy: government spending newsletter (Beehiiv) + data products (Apify/RapidAPI).
Architecture: custom Python orchestration, no frameworks. "LLM proposes, deterministic code executes."

## Current State
- Core orchestration layer COMPLETE and running (coordinator + 4 subagents)
- Decision loop works: WAKE → ASSESS → PLAN → EXECUTE → REPORT
- Model router works: local qwen3:4b via Anthropic SDK + cloud claude-haiku-4-5
- Discord reporting LIVE (bot posts to #commands channel)
- SQLite state tracking LIVE (task log, cost log, escalation queue)
- GitHub repo: github.com/toby20frame/thoth-v2 (private)
- All code at /mnt/nvme/thoth/core/

## What Works
- Full decision cycle completes successfully
- Local model (qwen3:4b) handles planning via Anthropic SDK
- Cloud Claude (haiku-4-5) routes correctly, costs tracked
- Thinking block filtering works (/no_think + text block extraction)
- Discord bot posts reports to #commands
- Git repo set up and pushing

## Known Issues
- Local model outputs are mostly empty (thinking tokens consume budget)
- LOCAL_MAX_TOKENS may need increase, or switch to qwen2.5-coder:3b for structured tasks
- Subagent outputs not captured in result_summary field
- USAspending.gov tools defined but not yet tested with real API calls
- Discord listener still running old OpenClaw version (not yet migrated)
- No calibration data yet
- Memory system (thoth_memory.db) exists but not populated
- Claude Code research pipeline not yet wired in

## Tech Stack
- Jetson Orin Nano 8GB, JetPack 6.2, Ubuntu 22.04, Python 3.10
- NVMe 1TB at /mnt/nvme (854GB free)
- Ollama 0.16.1: qwen3:4b, qwen2.5-coder:3b, nomic-embed-text
- anthropic SDK 0.86.0 (unified for local + cloud)
- ANTHROPIC_API_KEY in environment (claude-haiku-4-5 confirmed working)
- Claude Code CLI 2.1.63 (authenticated, headless mode available)
- Tailscale for remote access
- SearXNG in Docker for self-hosted search
- Cursor SSH for development

## Key Decisions Made (Do Not Revisit)
- No frameworks (no LangChain, CrewAI, PydanticAI, SmolAgents)
- Raw Anthropic SDK for everything (Ollama speaks Anthropic API)
- SQLite for all state (WAL mode)
- Government spending newsletter as primary revenue strategy
- Data products on Apify Store as secondary revenue
- Custom Python orchestration (~500 lines, 14 files)
- Operator experience > pure autonomy
- Satisficing over optimizing for strategy selection
- Hardcoded constraints in code, not prompt-based constitution
- Calibration matrix to earn autonomy levels

## Next Priorities (In Order)
1. Fix local model output quality (thinking token issue)
2. Test USAspending.gov API tools with real data
3. Run a real cycle that produces meaningful output
4. Start calibration phase (10-15 tasks across capability areas)
5. Migrate Discord listener to use new coordinator
6. Wire Claude Code research pipeline
7. Build newsletter generation pipeline
8. Build first data product MVP

## Research Completed (10 deep research prompts)
1. Agent economics and failure modes
2. Viable revenue domains for resource-constrained agents
3. Memory systems for autonomous agents (hybrid SQLite + FTS5 + sqlite-vec)
4. LLM API pricing and model routing optimization
5. Data product validation and launch strategy
6. Agent orchestration frameworks (conclusion: don't use one)
7. Financial newsletter niche selection (government spending won)
8. Production data pipelines on Jetson
9. Claude Code CLI as research engine
10. Scaffolding comparison (raw API + Pydantic BaseModel won)

## Files
- /mnt/nvme/thoth/core/ — all orchestration code
- /mnt/nvme/thoth/data/ — SQLite databases
- ~/thoth/builder-spec.md — the spec Cursor used to build
- Research outputs — saved in this conversation (re-share if needed)
