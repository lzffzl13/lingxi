from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Base class for all tools."""
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """Execute tool and return text result."""
        ...

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function calling tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# Tool registry
_tool_registry: dict[str, BaseTool] = {}


def register_tool(cls):
    """Decorator to register a tool class."""
    instance = cls()
    _tool_registry[instance.name] = instance
    return cls


def get_all_tools() -> list[dict]:
    """Get all registered tools in OpenAI format."""
    return [t.to_openai_tool() for t in _tool_registry.values()]


def get_tool(name: str) -> BaseTool | None:
    """Get a tool by name."""
    return _tool_registry.get(name)


async def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with given arguments."""
    tool = _tool_registry.get(name)
    if not tool:
        return f"Error: tool '{name}' not found"
    try:
        return await tool.execute(**arguments)
    except Exception as e:
        return f"Error executing tool '{name}': {str(e)}"
