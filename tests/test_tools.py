import pytest
from app.tools.base import execute_tool, get_all_tools


class TestCheckOrder:
    @pytest.mark.asyncio
    async def test_found(self):
        result = await execute_tool("check_order", {"order_id": "ORD-20240101-001"})
        assert "已发货" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        result = await execute_tool("check_order", {"order_id": "不存在"})
        assert "未找到" in result


class TestTransferHuman:
    @pytest.mark.asyncio
    async def test_transfer(self):
        result = await execute_tool("transfer_to_human", {"reason": "用户投诉"})
        assert "转接" in result


class TestToolRegistry:
    def test_all_tools_registered(self):
        tools = get_all_tools()
        names = [t["function"]["name"] for t in tools]
        assert "check_order" in names
        assert "transfer_to_human" in names

    def test_unknown_tool(self):
        import asyncio
        result = asyncio.run(execute_tool("unknown_tool", {}))
        assert "not found" in result
