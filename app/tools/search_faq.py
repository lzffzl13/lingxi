"""FAQ search tool for knowledge base retrieval."""

from app.tools.base import BaseTool, register_tool
from app.knowledge.manager import KnowledgeManager

# Global knowledge manager instance
_knowledge_manager: KnowledgeManager | None = None


def set_knowledge_manager(manager: KnowledgeManager) -> None:
    """Set the global knowledge manager instance."""
    global _knowledge_manager
    _knowledge_manager = manager


@register_tool
class SearchFaqTool(BaseTool):
    """搜索常见问题解答（FAQ）知识库。"""

    name = "search_faq"
    description = "根据用户问题搜索知识库中的相关FAQ答案"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或问题",
            }
        },
        "required": ["query"],
    }

    async def execute(self, query: str) -> str:
        """Search FAQ knowledge base."""
        if _knowledge_manager is None:
            return '{"error": "知识库未初始化"}'

        results = await _knowledge_manager.search(query)
        if not results:
            return '{"message": "未找到相关FAQ"}'

        import json
        return json.dumps(results, ensure_ascii=False)
