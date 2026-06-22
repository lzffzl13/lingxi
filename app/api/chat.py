from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import AgentDep
from app.models.schemas import ChatRequest, ChatResponse
from app.utils.logger import logger
from app.security import sanitize_input, validate_message_length

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, agent: AgentDep):
    """Handle chat request (non-streaming)."""
    # Sanitize and validate input
    message = sanitize_input(request.message)
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if not validate_message_length(message):
        raise HTTPException(status_code=400, detail="Message too long")

    try:
        response = await agent.run(
            session_id=request.session_id,
            user_message=message,
        )
        return response
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, agent: AgentDep):
    """Handle chat request with SSE streaming response.

    Event types:
    - token: partial text content
    - tool: tool call execution result
    - done: conversation turn complete
    """
    # Sanitize and validate input
    message = sanitize_input(request.message)
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if not validate_message_length(message):
        raise HTTPException(status_code=400, detail="Message too long")

    try:
        async def event_generator():
            async for event in agent.run_stream(
                session_id=request.session_id,
                user_message=message,
            ):
                yield event

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        logger.error(f"Chat stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
