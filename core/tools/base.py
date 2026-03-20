# Global registries
TOOL_REGISTRY = {}   # agent_name -> list of tool JSON schemas
TOOL_DISPATCH = {}   # tool_name -> callable


def register_tool(agent_name: str, schema: dict, execute_fn: callable):
    if agent_name not in TOOL_REGISTRY:
        TOOL_REGISTRY[agent_name] = []
    TOOL_REGISTRY[agent_name].append(schema)
    TOOL_DISPATCH[schema["name"]] = execute_fn

