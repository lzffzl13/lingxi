class AgentError(Exception):
    """Base exception for agent runtime errors."""
    pass


class LLMCallError(AgentError):
    """LLM call failed."""
    pass


class SessionError(AgentError):
    """Session related error."""
    pass
