from app.models.message import Message

# Base system prompt
SYSTEM_PROMPT = """你是「灵犀」智能客服，态度友善专业，回复简洁，通常控制在 2 到 3 句话内。

## 能力
- 查询订单：使用 `check_order` 工具，需要订单号。
- 搜索 FAQ：使用 `search_faq` 工具，用户询问常见问题时优先使用。
- 检查退换货资格：使用 `check_return_eligibility` 工具，需要订单号。
- 创建退换货工单：使用 `create_return` 工具。
- 转人工：使用 `transfer_to_human` 工具。

## 规则
1. 不要编造信息，不确定时直接说明。
2. 无法处理的问题及时转人工。
3. 涉及退款、修改订单等高风险操作时，优先转人工。
4. 始终使用中文回复，语气自然、清晰、礼貌。
5. 订单号格式示例：`ORD-YYYYMMDD-XXX`。

## 场景引导
- 用户提供订单号时，主动查询订单状态。
- 用户提到退货、换货、退款时，先查询订单，再判断资格。
- 用户询问常见规则或流程时，优先搜索 FAQ 后再回答。
"""

SCENE_TEMPLATES = {
    "order_inquiry": "用户正在查询订单信息，请优先给出订单状态、物流进度和下一步建议。",
    "return_request": "用户想办理退换货，请先核对订单状态，再检查退换货资格。",
    "faq_question": "用户在询问常见问题，请优先搜索 FAQ 知识库获取更准确的答案。",
    "complaint": "用户可能存在投诉或明显不满，请保持耐心，必要时及时转人工。",
}


def detect_scene(user_message: str) -> str | None:
    """Detect conversation scene from user message."""
    if not user_message:
        return None

    if any(kw in user_message for kw in ["订单", "查一下", "物流", "快递", "到哪"]):
        return "order_inquiry"

    if any(kw in user_message for kw in ["退货", "换货", "退款", "退掉"]):
        return "return_request"

    if any(kw in user_message for kw in ["怎么", "如何", "多久", "可以", "能不能"]):
        return "faq_question"

    if any(kw in user_message for kw in ["投诉", "不满", "差评", "垃圾", "骗人"]):
        return "complaint"

    return None


def build_messages(
    system_prompt: str,
    history: list[Message],
    user_message: str,
) -> list[dict]:
    """Build messages list for LLM from system prompt, history, and new user message."""
    messages = [{"role": "system", "content": system_prompt}]

    scene = detect_scene(user_message)
    if scene and scene in SCENE_TEMPLATES:
        messages.append(
            {
                "role": "system",
                "content": f"[场景提示] {SCENE_TEMPLATES[scene]}",
            }
        )

    for msg in history[-5:]:
        messages.append({"role": msg.role.value, "content": msg.content})

    messages.append({"role": "user", "content": user_message})
    return messages
