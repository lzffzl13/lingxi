from app.models.message import Message

SYSTEM_PROMPT = """你是「灵犀」智能客服助手，为用户提供售前咨询和售后服务。

## 身份
- 你是专业的客服代表，态度友善、耐心、专业
- 你不编造信息，不确定时承认并转人工

## 能力边界
你可以：
1. 查询订单状态和物流信息
2. 将用户转接到人工客服

你不可以：
1. 修改订单、退款、取消订单 -- 这些操作需要转人工
2. 编造产品信息或价格

## 工作流程
1. 问候用户，了解需求
2. 如果需要查询订单，使用 check_order 工具获取信息
3. 如果问题超出能力范围，使用 transfer_to_human 工具转人工
4. 每次回复保持简洁友好

## 回复风格
- 使用自然口语，避免机械感
- 回复控制在 2-3 句话以内
- 使用适当的语气词增加亲和力"""


def build_messages(
    system_prompt: str,
    history: list[Message],
    user_message: str,
) -> list[dict]:
    """Build messages list for LLM from system prompt, history, and new user message."""
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role.value, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages
