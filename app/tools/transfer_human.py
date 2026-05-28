import json
from app.tools.base import BaseTool, register_tool


@register_tool
class TransferHumanTool(BaseTool):
    """将用户转接到人工客服。"""
    name = "transfer_to_human"
    description = "将用户转接到人工客服。当问题超出智能客服能力范围时使用。"
    parameters = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "转人工的原因",
            }
        },
        "required": ["reason"],
    }

    async def execute(self, reason: str) -> str:
        return json.dumps({
            "status": "transferred",
            "message": f"已为您转接人工客服，原因: {reason}。请稍候，人工客服即将接入。",
        }, ensure_ascii=False)
