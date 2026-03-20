import anthropic
import time
from config import (
    LOCAL_MODEL, LOCAL_BASE_URL, LOCAL_MAX_TOKENS,
    CLOUD_MODEL, CLOUD_FALLBACK_MODEL, MODEL_COSTS,
    MAX_RETRIES_PER_TASK
)


def extract_text(response) -> str:
    """Extract text from response, filtering out thinking blocks.
    CRITICAL: Ollama qwen3:4b returns ThinkingBlock objects.
    Never access response.content[0].text directly.
    """
    text_parts = []
    for block in response.content:
        if block.type == "text" and hasattr(block, "text"):
            text_parts.append(block.text)
    return "\n".join(text_parts).strip()


class ModelRouter:
    def __init__(self):
        self.local = anthropic.Anthropic(
            base_url=LOCAL_BASE_URL,
            api_key="ollama"
        )
        # Cloud client picks up ANTHROPIC_API_KEY from environment
        self.cloud = anthropic.Anthropic()

    def classify_complexity(self, task: str, force_cloud: bool = False) -> str:
        if force_cloud:
            return "complex"
        simple_signals = [
            "summarize", "format", "extract", "classify", "list",
            "count", "parse", "convert", "filter", "check"
        ]
        task_lower = task.lower()
        if len(task) < 500 and any(s in task_lower for s in simple_signals):
            return "simple"
        complex_signals = [
            "analyze", "compare", "recommend", "evaluate", "write",
            "generate newsletter", "research", "plan", "strategy"
        ]
        if any(s in task_lower for s in complex_signals):
            return "complex"
        if len(task) > 1500:
            return "complex"
        return "simple"

    def call(self, messages: list, system: str = "", tools: list = None,
             force_cloud: bool = False, max_tokens: int = None) -> dict:
        """
        Make an LLM call routed to the appropriate model.
        Returns dict: response, model_used, input_tokens, output_tokens, cost_usd, text
        """
        complexity = self.classify_complexity(
            messages[-1]["content"] if messages else "",
            force_cloud=force_cloud
        )

        is_local = (complexity == "simple")

        if is_local:
            client = self.local
            model = LOCAL_MODEL
            effective_max_tokens = max_tokens or LOCAL_MAX_TOKENS
            # Append /no_think to suppress thinking on local model
            messages = _append_no_think(messages)
        else:
            client = self.cloud
            model = CLOUD_MODEL
            effective_max_tokens = max_tokens or 2048

        kwargs = {
            "model": model,
            "max_tokens": effective_max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools and not is_local:
            # Only pass tools to cloud model — local models struggle with tool schemas
            kwargs["tools"] = tools

        # Retry with backoff
        response = None
        for attempt in range(MAX_RETRIES_PER_TASK):
            try:
                response = client.messages.create(**kwargs)
                break
            except anthropic.RateLimitError:
                time.sleep(2 ** attempt)
            except anthropic.APIConnectionError:
                if is_local:
                    # Local Ollama down — fall back to cloud
                    client = self.cloud
                    model = CLOUD_MODEL
                    kwargs["model"] = model
                    kwargs["max_tokens"] = max_tokens or 2048
                    # Remove /no_think for cloud
                    kwargs["messages"] = messages  # Original without /no_think
                    try:
                        response = client.messages.create(**kwargs)
                        break
                    except Exception:
                        raise
                if attempt == MAX_RETRIES_PER_TASK - 1:
                    raise
                time.sleep(1)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    time.sleep(2 ** attempt)
                elif e.status_code == 404 and model == CLOUD_MODEL:
                    # Model not found, try fallback
                    model = CLOUD_FALLBACK_MODEL
                    kwargs["model"] = model
                    response = client.messages.create(**kwargs)
                    break
                else:
                    raise

        if response is None:
            return {
                "response": None,
                "model_used": model,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0,
                "text": "ERROR: API unreachable after retries",
            }

        # Calculate cost
        costs = MODEL_COSTS.get(model, {"input": 0, "output": 0})
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000

        return {
            "response": response,
            "model_used": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "text": extract_text(response),
        }


def _append_no_think(messages: list) -> list:
    """Append /no_think to the last user message for local model calls."""
    if not messages:
        return messages
    modified = [m.copy() for m in messages]
    last = modified[-1]
    if last.get("role") == "user" and isinstance(last.get("content"), str):
        if "/no_think" not in last["content"]:
            last["content"] = last["content"] + " /no_think"
    return modified

