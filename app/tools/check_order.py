"""Check order tool - queries database for order information."""

import json
from app.tools.base import BaseTool, register_tool
from app.db.database import async_session_factory
from app.db.repositories import OrderRepository


@register_tool
class CheckOrderTool(BaseTool):
    """查询订单状态和物流信息。"""

    name = "check_order"
    description = "根据订单号查询订单状态、物流信息"
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

    # Fallback mock data for when database is not available
    MOCK_ORDERS = {
        "ORD-20240101-001": {
            "status": "已发货",
            "tracking": "SF1234567890",
            "items": "蓝牙耳机 x1",
            "total": "299.00",
        },
        "ORD-20240102-002": {
            "status": "待发货",
            "tracking": "",
            "items": "手机壳 x2",
            "total": "58.00",
        },
        "ORD-20240103-003": {
            "status": "已签收",
            "tracking": "YT9876543210",
            "items": "充电宝 x1",
            "total": "159.00",
        },
    }

    async def execute(self, order_id: str) -> str:
        """Query order from database or fallback to mock data."""
        # Try database first
        if async_session_factory:
            try:
                async with async_session_factory() as session:
                    repo = OrderRepository(session)
                    order = await repo.get_by_id(order_id)
                    if order:
                        return json.dumps(order.to_dict(), ensure_ascii=False)
            except Exception:
                pass  # Fall through to mock data

        # Fallback to mock data
        order = self.MOCK_ORDERS.get(order_id)
        if order:
            return json.dumps(order, ensure_ascii=False)
        return json.dumps({"error": "未找到该订单"}, ensure_ascii=False)
