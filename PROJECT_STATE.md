# Thoth V2 — Project State

**Last updated:** March 20, 2026

## Next Session Gameplan
Start here. These are the specific tasks for the next work session, in order:

1. **Fix local model empty outputs.** The qwen3:4b thinking tokens eat the entire budget. Either increase LOCAL_MAX_TOKENS from 500 to 1500, or test qwen2.5-coder:3b (no thinking blocks). Test with: `cd ~/thoth/core && python3 main.py`
2. **Fix newsletter date.** The newsletter agent generated "December 19, 2024" instead of current date. Add current date to the newsletter agent's system prompt or task description.
3. **Run a full cycle that produces a readable newsletter draft.** Save the output to a file so we can evaluate quality.
4. **Start calibration.** Run 5 specific tasks manually (API fetch, data analysis, newsletter draft, summarization, system check) and score the outputs.
5. **If time: migrate Discord listener** from old OpenClaw bot to V2 coordinator.

## What Thoth Is
A constrained, semi-autonomous economic agent on a Jetson Orin Nano 8GB.
Revenue strategy: government spending newsletter (Beehiiv) + data products (Apify/RapidAPI).
Architecture: custom Python orchestration, no frameworks. "LLM proposes, deterministic code executes."

## Current State
- Core orchestration layer COMPLETE and running (14 files, ~2100 lines)
- Decision loop works: WAKE → ASSESS → PLAN → EXECUTE → REPORT
- Model router: local qwen3:4b + cloud claude-haiku-4-5
- Research agent PULLING REAL DATA from USAspending.gov via tools
- Newsletter agent GENERATING REAL CONTENT (Daily Financial Briefing)
- Discord reporting LIVE (bot posts to #commands channel)
- SQLite state tracking LIVE with cost logging (~$0.01 per cycle)
- GitHub repo: github.com/toby20frame/thoth-v2 (PUBLIC)
- Session continuity working (Claude project fetches from GitHub)

## What Works
- Full decision cycle with real API data
- Research/newsletter route to cloud, system/data stay local
- USAspending.gov tool calls returning real spending data
- Thinking block filtering (/no_think + text extraction)
- Discord bot posts cycle reports
- Git workflow: Cursor SSH → edit → commit → push

## Known Issues
- Local model outputs empty (thinking tokens consume budget)
- Newsletter uses wrong date
- Data processing task gets no data passed to it
- Discord listener still old OpenClaw version
- Memory system unpopulated
- Claude Code research pipeline not wired
- Architecture doc in wrong location (core/tools/ instead of repo root)

## Key Decisions (Do Not Revisit)
- No frameworks — raw Anthropic SDK
- Ollama speaks Anthropic API (unified SDK)
- SQLite WAL mode for all state
- Government spending newsletter primary revenue
- Data products on Apify secondary
- Research/newsletter force cloud, system/data stay local
- Hardcoded constraints in code
- Calibration matrix earns autonomy

## Tech Stack
- Jetson Orin Nano 8GB, JetPack 6.2, Ubuntu 22.04, Python 3.10
- NVMe 1TB at /mnt/nvme, Ollama 0.16.1 (qwen3:4b, qwen2.5-coder:3b, nomic-embed-text)
- anthropic 0.86.0, ANTHROPIC_API_KEY in env, claude-haiku-4-5 working
- Claude Code CLI 2.1.63, Tailscale, SearXNG, Cursor SSH
