"""Tool registry and ecommerce tool tests."""

import asyncio
import json
from datetime import datetime, timedelta

import pytest

from app.tools.base import execute_tool, get_all_tools, get_tool
from app.tools.check_return import CheckReturnEligibilityTool


class TestCheckOrder:
    @pytest.mark.asyncio
    async def test_found(self):
        result = await execute_tool("check_order", {"order_id": "ORD-20240101-001"})
        data = json.loads(result)

        assert data["tracking"] == "SF1234567890"
        assert data["total"] == "299.00"
        assert "status" in data

    @pytest.mark.asyncio
    async def test_not_found(self):
        result = await execute_tool("check_order", {"order_id": "missing-order"})
        data = json.loads(result)

        assert "error" in data


class TestTransferHuman:
    @pytest.mark.asyncio
    async def test_transfer(self):
        result = await execute_tool("transfer_to_human", {"reason": "complaint"})
        data = json.loads(result)

        assert data["status"] == "transferred"
        assert "complaint" in data["message"]


class TestCheckReturn:
    @pytest.mark.asyncio
    async def test_fallback_when_database_unavailable(self):
        result = await execute_tool(
            "check_return_eligibility", {"order_id": "ORD-20240103-003"}
        )
        data = json.loads(result)

        assert data["eligible"] is False
        assert data["order_id"] == "ORD-20240103-003"
        assert "reason" in data

    def test_delivered_order_is_eligible_within_policy_window(self):
        tool = CheckReturnEligibilityTool()
        order = {
            "id": "ORD-1",
            "status": "delivered",
            "updated_at": datetime.now().isoformat(),
            "items": [{"sku": "SKU-1", "quantity": 1}],
        }

        data = json.loads(tool._check_eligibility(order))

        assert data["eligible"] is True
        assert data["order_id"] == "ORD-1"
        assert data["return_policy_days"] == tool.RETURN_POLICY_DAYS

    def test_undelivered_order_is_not_eligible(self):
        tool = CheckReturnEligibilityTool()
        order = {
            "id": "ORD-1",
            "status": "pending",
            "updated_at": datetime.now().isoformat(),
        }

        data = json.loads(tool._check_eligibility(order))

        assert data["eligible"] is False
        assert data["order_id"] == "ORD-1"

    def test_delivered_order_after_policy_window_is_not_eligible(self):
        tool = CheckReturnEligibilityTool()
        order = {
            "id": "ORD-1",
            "status": "delivered",
            "updated_at": (
                datetime.now() - timedelta(days=tool.RETURN_POLICY_DAYS + 1)
            ).isoformat(),
        }

        data = json.loads(tool._check_eligibility(order))

        assert data["eligible"] is False
        assert data["order_id"] == "ORD-1"
        assert "deadline" in data


class TestCreateReturn:
    @pytest.mark.asyncio
    async def test_create_refund(self):
        result = await execute_tool(
            "create_return",
            {
                "order_id": "ORD-20240103-003",
                "reason": "quality issue",
                "return_type": "refund",
            },
        )
        data = json.loads(result)

        assert data["success"] is True
        assert data["return_id"].startswith("RET-")

    @pytest.mark.asyncio
    async def test_create_exchange(self):
        result = await execute_tool(
            "create_return",
            {
                "order_id": "ORD-20240103-003",
                "reason": "wrong size",
                "return_type": "exchange",
            },
        )
        data = json.loads(result)

        assert data["success"] is True
        assert data["return_id"].startswith("RET-")


class TestToolRegistry:
    def test_all_tools_registered(self):
        tools = get_all_tools()
        names = [t["function"]["name"] for t in tools]

        assert "check_order" in names
        assert "transfer_to_human" in names
        assert "search_faq" in names
        assert "check_return_eligibility" in names
        assert "create_return" in names

    def test_get_tool(self):
        tool = get_tool("check_order")

        assert tool is not None
        assert tool.name == "check_order"

    def test_unknown_tool(self):
        result = asyncio.run(execute_tool("unknown_tool", {}))

        assert "not found" in result

    def test_tool_argument_errors_are_returned(self):
        result = asyncio.run(execute_tool("check_order", {}))

        assert result.startswith("Error executing tool 'check_order'")
