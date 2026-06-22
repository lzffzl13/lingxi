"""Knowledge base manager using simple keyword matching with caching."""

import time
from functools import lru_cache

from app.config import Settings
from app.utils.logger import logger


# FAQ database
FAQ_DATABASE = [
    {
        "question": "如何查询订单状态？",
        "answer": "您可以通过提供订单号来查询订单状态。例如：帮我查一下订单 ORD-20240101-001 的状态。",
        "category": "订单查询",
        "keywords": ["订单", "查询", "状态", "物流"]
    },
    {
        "question": "订单什么时候能到？",
        "answer": "普通快递一般3-5个工作日送达，顺丰快递1-2个工作日送达。具体时效以物流信息为准。",
        "category": "物流配送",
        "keywords": ["物流", "配送", "到货", "时效", "快递"]
    },
    {
        "question": "可以退货吗？",
        "answer": "自商品签收之日起7天内，商品未使用且包装完好的情况下可以申请无理由退货。",
        "category": "退换货",
        "keywords": ["退货", "退款", "退换", "七天", "无理由"]
    },
    {
        "question": "退款多久到账？",
        "answer": "退款审核通过后，一般1-3个工作日到账。具体到账时间取决于支付方式和银行处理速度。",
        "category": "退款",
        "keywords": ["退款", "到账", "时间", "多久"]
    },
    {
        "question": "如何修改收货地址？",
        "answer": "订单未发货前可以修改收货地址。请联系客服提供订单号和新地址进行修改。",
        "category": "订单管理",
        "keywords": ["地址", "修改", "收货", "变更"]
    },
    {
        "question": "发票怎么开？",
        "answer": "下单时可以选择开具电子发票，订单完成后会发送到您的邮箱。如需补开，请联系客服。",
        "category": "发票",
        "keywords": ["发票", "开具", "电子发票"]
    },
    {
        "question": "会员有什么优惠？",
        "answer": "会员享受专属折扣、积分兑换、优先发货等权益。消费满1000元可升级为金牌会员。",
        "category": "会员",
        "keywords": ["会员", "优惠", "折扣", "积分", "权益"]
    },
    {
        "question": "商品有质量问题怎么办？",
        "answer": "收到商品如有质量问题，请在7天内联系客服，提供照片凭证，我们会尽快为您处理退换货。",
        "category": "售后服务",
        "keywords": ["质量", "问题", "损坏", "售后"]
    },
]


class SearchCache:
    """Simple TTL cache for search results."""

    def __init__(self, ttl: int = 300, max_size: int = 100):
        """Initialize cache.

        Args:
            ttl: Time to live in seconds (default 5 minutes)
            max_size: Maximum cache entries
        """
        self._cache: dict[str, tuple[float, list]] = {}
        self._ttl = ttl
        self._max_size = max_size

    def get(self, key: str) -> list | None:
        """Get cached result if valid."""
        if key in self._cache:
            timestamp, result = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return result
            else:
                # Expired
                del self._cache[key]
        return None

    def set(self, key: str, result: list) -> None:
        """Cache a result."""
        # Evict oldest entries if cache is full
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

        self._cache[key] = (time.time(), result)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


class KnowledgeManager:
    """Manages FAQ knowledge base with keyword matching and caching."""

    def __init__(self, config: Settings):
        self.config = config
        self._cache = SearchCache(ttl=300, max_size=100)

    async def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Search FAQ using keyword matching with caching.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of matching FAQ entries with scores
        """
        k = top_k or self.config.KNOWLEDGE_TOP_K
        cache_key = f"{query.lower()}:{k}"

        # Check cache first
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for query: {query}")
            return cached

        # Perform search
        query_lower = query.lower()
        results = []
        for faq in FAQ_DATABASE:
            score = 0
            for keyword in faq["keywords"]:
                if keyword in query_lower:
                    score += 1

            if score > 0:
                results.append({
                    "question": faq["question"],
                    "answer": faq["answer"],
                    "category": faq["category"],
                    "score": score / len(faq["keywords"])
                })

        # Sort by score and return top k
        results.sort(key=lambda x: x["score"], reverse=True)
        final_results = results[:k]

        # Cache results
        self._cache.set(cache_key, final_results)

        return final_results

    def clear_cache(self) -> None:
        """Clear the search cache."""
        self._cache.clear()
        logger.info("Knowledge search cache cleared")
