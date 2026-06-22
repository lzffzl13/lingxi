"""Check return eligibility tool - queries database for order information."""

import json
from datetime import datetime, timedelta
from app.tools.base import BaseTool, register_tool
from app.db.database import async_session_factory
from app.db.repositories import OrderRepository


@register_tool
class CheckReturnEligibilityTool(BaseTool):
    """检查订单是否符合退换货条件。"""

    name = "check_return_eligibility"
    description = "根据订单号检查是否符合退换货条件"
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "订单号，例如 ORD-20240101-001",
            }
        },
        "required": ["order_id"],
    }

    RETURN_POLICY_DAYS = 7

    async def execute(self, order_id: str) -> str:
        """Check return eligibility for an order."""
        # Try database first
        if async_session_factory:
            try:
                async with async_session_factory() as session:
                    repo = OrderRepository(session)
                    order = await repo.get_by_id(order_id)
                    if order:
                        return self._check_eligibility(order.to_dict())
            except Exception:
                pass

        # Fallback to mock check
        return json.dumps({
            "eligible": False,
            "reason": "数据库未连接，无法查询订单",
            "order_id": order_id,
        }, ensure_ascii=False)

    def _check_eligibility(self, order: dict) -> str:
        """Check if order is eligible for return."""
        # Check if order is delivered
        if order["status"] != "delivered":
            return json.dumps({
                "eligible": False,
                "reason": "商品尚未签收，无法申请退换货",
                "order_id": order["id"],
            }, ensure_ascii=False)

        # Check if within return window (7 days from delivery)
        if order.get("updated_at"):
            updated_at = datetime.fromisoformat(order["updated_at"])
            return_deadline = updated_at + timedelta(days=self.RETURN_POLICY_DAYS)
            if datetime.now() > return_deadline:
                return json.dumps({
                    "eligible": False,
                    "reason": f"已超过{self.RETURN_POLICY_DAYS}天退换货期限",
                    "order_id": order["id"],
                    "deadline": return_deadline.strftime("%Y-%m-%d"),
                }, ensure_ascii=False)

        return json.dumps({
            "eligible": True,
            "reason": "符合退换货条件",
            "order_id": order["id"],
            "items": order.get("items"),
            "return_policy_days": self.RETURN_POLICY_DAYS,
        }, ensure_ascii=False)
