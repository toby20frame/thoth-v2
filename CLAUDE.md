# Instructions for AI Assistants Working on Thoth V2

Read PROJECT_STATE.md first. It contains current system state and known issues.

## Architecture Rules (Non-Negotiable)
These were decided after extensive research and must not be changed without explicit discussion:

1. **No frameworks.** Raw Anthropic SDK only. No LangChain, CrewAI, PydanticAI, SmolAgents.
2. **Ollama via Anthropic SDK.** base_url="http://localhost:11434", api_key="ollama"
3. **Cloud via env var.** anthropic.Anthropic() picks up ANTHROPIC_API_KEY automatically.
4. **Handle thinking blocks.** qwen3:4b returns ThinkingBlock objects. Always filter: [b.text for b in resp.content if b.type == "text"]
5. **Append /no_think to local prompts.** Saves tokens on qwen3:4b.
6. **SQLite for all state.** WAL mode. Databases at ~/thoth/data/. Never recreate them.
7. **"LLM proposes, deterministic code executes."** LLM returns JSON, Python executes.
8. **Every API call logged with token counts and cost.**
9. **Pydantic BaseModel for validation only.** Not the PydanticAI framework.
10. **Hardcoded constraints in code.** Not prompt-based constitution.

## Working Models
- Local: qwen3:4b (Ollama, port 11434)
- Cloud cheap: claude-haiku-4-5
- Cloud fallback: claude-3-haiku-20240307
- Claude Code CLI: v2.1.63 (for research pipeline, authenticated)

## Project Structure
- /mnt/nvme/thoth/core/ — orchestration code (14 Python files)
- /mnt/nvme/thoth/data/ — SQLite databases (state, memory, calibration)
- /mnt/nvme/thoth/pipelines/ — data pipelines (not yet built)
- /mnt/nvme/thoth/research/ — research outputs

## Development Workflow
- Edit via Cursor SSH to thoth@100.71.80.47
- Test: cd ~/thoth/core && python3 main.py
- Commit: cd ~/thoth && git add -A && git commit -m "message" && git push
- Discord reports post to #commands channel automatically

## Do NOT
- Install new frameworks without discussion
- Recreate or drop SQLite databases
- Store credentials in code or git
- Use OpenAI SDK (Ollama speaks Anthropic format)
- Access response.content[0].text directly (thinking blocks will crash)
