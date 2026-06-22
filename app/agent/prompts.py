from app.models.message import Message

# Base system prompt
SYSTEM_PROMPT = """你是「灵犀」智能客服，态度友善专业，回复简洁（2-3句话）。

## 能力
- **查询订单**：用 check_order 工具，需要订单号
- **搜索FAQ**：用 search_faq 工具，用户问常见问题时优先使用
- **检查退换货资格**：用 check_return_eligibility 工具，需要订单号
- **创建退换货工单**：用 create_return 工具
- **转人工**：用 transfer_to_human 工具

## 规则
1. 不要编造信息，不确定就说不确定
2. 无法处理的问题及时转人工
3. 涉及退款、修改订单等操作，必须转人工
4. 回复使用中文，语气亲切自然
5. 订单号格式：ORD-YYYYMMDD-XXX

## 场景引导
- 用户提供订单号时，主动查询订单状态
- 用户提到"退货/换货/退款"时，先查询订单再判断资格
- 用户问常见问题时，先搜索FAQ再回答"""

# Context-aware prompt templates
SCENE_TEMPLATES = {
    "order_inquiry": "用户正在查询订单信息，请提供订单状态和物流信息。",
    "return_request": "用户想退换货，请先查询订单状态，再检查退换货资格。",
    "faq_question": "用户在问常见问题，请搜索FAQ知识库获取答案。",
    "complaint": "用户可能有投诉或不满，请保持耐心，必要时转人工。",
}


def detect_scene(user_message: str) -> str | None:
    """Detect conversation scene from user message.

    Returns scene name or None if no specific scene detected.
    """
    msg_lower = user_message.lower()

    # Order inquiry keywords
    if any(kw in msg_lower for kw in ["订单", "查一下", "物流", "快递", "到哪"]):
        return "order_inquiry"

    # Return request keywords
    if any(kw in msg_lower for kw in ["退货", "换货", "退款", "退换"]):
        return "return_request"

    # FAQ keywords
    if any(kw in msg_lower for kw in ["怎么", "如何", "多久", "可以", "能不能"]):
        return "faq_question"

    # Complaint keywords
    if any(kw in msg_lower for kw in ["投诉", "不满", "差评", "垃圾", "骗"]):
        return "complaint"

    return None


def build_messages(
    system_prompt: str,
    history: list[Message],
    user_message: str,
) -> list[dict]:
    """Build messages list for LLM from system prompt, history, and new user message.

    Dynamically adds scene context based on user message.
    """
    messages = [{"role": "system", "content": system_prompt}]

    # Add scene context if detected
    scene = detect_scene(user_message)
    if scene and scene in SCENE_TEMPLATES:
        messages.append({
            "role": "system",
            "content": f"[场景提示] {SCENE_TEMPLATES[scene]}"
        })

    # Keep last 5 history messages for context window
    for msg in history[-5:]:
        messages.append({"role": msg.role.value, "content": msg.content})

    messages.append({"role": "user", "content": user_message})
    return messages
