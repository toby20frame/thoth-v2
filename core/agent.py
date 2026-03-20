import json
import time
from router import ModelRouter, extract_text
from config import MAX_AGENT_ITERATIONS, MAX_RETRIES_PER_TASK


class SubAgent:
    def __init__(self, router: ModelRouter, name: str, system_prompt: str,
                 tools: list = None, tool_dispatch: dict = None,
                 force_cloud: bool = False):
        self.router = router
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.tool_dispatch = tool_dispatch or {}
        self.force_cloud = force_cloud
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.model_used = ""

    def run(self, task: str) -> str:
        """Run the agent loop. Returns the final text response."""
        messages = [{"role": "user", "content": task}]

        for iteration in range(MAX_AGENT_ITERATIONS):
            result = self.router.call(
                messages=messages,
                system=self.system_prompt,
                tools=self.tools if self.tools else None,
                force_cloud=self.force_cloud,
            )

            response = result["response"]
            if response is None:
                return result["text"]  # Error message

            self.model_used = result["model_used"]
            self.total_input_tokens += result["input_tokens"]
            self.total_output_tokens += result["output_tokens"]
            self.total_cost += result["cost_usd"]

            messages.append({"role": "assistant", "content": response.content})

            # If no tool use, we're done
            if response.stop_reason != "tool_use":
                return extract_text(response)

            # Execute tool calls
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                execute_fn = self.tool_dispatch.get(block.name)
                if execute_fn is None:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": f"Unknown tool: {block.name}"}),
                        "is_error": True,
                    })
                    continue

                # Retry loop for tool execution
                for attempt in range(MAX_RETRIES_PER_TASK):
                    try:
                        result_data = execute_fn(**block.input)
                        content = json.dumps(result_data) if isinstance(result_data, dict) else str(result_data)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content,
                        })
                        break
                    except Exception as e:
                        if attempt == MAX_RETRIES_PER_TASK - 1:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Tool failed after {MAX_RETRIES_PER_TASK} attempts: {e}",
                                "is_error": True,
                            })

            messages.append({"role": "user", "content": tool_results})

        return f"Agent '{self.name}' hit max iterations ({MAX_AGENT_ITERATIONS})"

