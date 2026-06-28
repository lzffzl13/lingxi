"""Data access layer (repositories) for database operations."""

from typing import Optional

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order, ReturnOrder, FAQ


class OrderRepository:
    """Repository for order operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        result = await self.session.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> list[Order]:
        """Get all orders for a user."""
        result = await self.session.execute(
            select(Order).where(Order.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create(self, order: Order) -> Order:
        """Create a new order."""
        self.session.add(order)
        await self.session.flush()
        return order

    async def update_status(self, order_id: str, status: str) -> bool:
        """Update order status."""
        result = await self.session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(status=status)
        )
        return result.rowcount > 0

    async def update_tracking(self, order_id: str, tracking_number: str) -> bool:
        """Update tracking number."""
        result = await self.session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(tracking_number=tracking_number)
        )
        return result.rowcount > 0


class ReturnOrderRepository:
    """Repository for return order operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, return_id: str) -> Optional[ReturnOrder]:
        """Get return order by ID."""
        result = await self.session.execute(
            select(ReturnOrder).where(ReturnOrder.id == return_id)
        )
        return result.scalar_one_or_none()

    async def get_by_order_id(self, order_id: str) -> list[ReturnOrder]:
        """Get all return orders for an order."""
        result = await self.session.execute(
            select(ReturnOrder).where(ReturnOrder.order_id == order_id)
        )
        return list(result.scalars().all())

    async def create(self, return_order: ReturnOrder) -> ReturnOrder:
        """Create a new return order."""
        self.session.add(return_order)
        await self.session.flush()
        return return_order

    async def update_status(self, return_id: str, status: str) -> bool:
        """Update return order status."""
        result = await self.session.execute(
            update(ReturnOrder)
            .where(ReturnOrder.id == return_id)
            .values(status=status)
        )
        return result.rowcount > 0


class FAQRepository:
    """Repository for FAQ operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, active_only: bool = True, limit: int | None = None, offset: int = 0) -> list[FAQ]:
        """Get all FAQs."""
        query = select(FAQ).order_by(FAQ.id)
        if active_only:
            query = query.where(FAQ.is_active.is_(True))
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, faq_id: int) -> Optional[FAQ]:
        """Get FAQ by ID."""
        result = await self.session.execute(
            select(FAQ).where(FAQ.id == faq_id)
        )
        return result.scalar_one_or_none()

    async def get_by_category(self, category: str) -> list[FAQ]:
        """Get FAQs by category."""
        result = await self.session.execute(
            select(FAQ).where(FAQ.category == category, FAQ.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def create(self, faq: FAQ) -> FAQ:
        """Create a new FAQ."""
        self.session.add(faq)
        await self.session.flush()
        return faq

    async def update(self, faq_id: int, **kwargs) -> bool:
        """Update FAQ."""
        result = await self.session.execute(
            update(FAQ).where(FAQ.id == faq_id).values(**kwargs)
        )
        return result.rowcount > 0

    async def delete(self, faq_id: int) -> bool:
        """Soft delete FAQ (set is_active=False)."""
        result = await self.session.execute(
            update(FAQ).where(FAQ.id == faq_id).values(is_active=False)
        )
        return result.rowcount > 0

    async def search(self, query: str) -> list[FAQ]:
        """Search FAQs by question, answer, or category content."""
        keyword = f"%{query}%"
        result = await self.session.execute(
            select(FAQ).where(
                FAQ.is_active.is_(True),
                or_(
                    FAQ.question.like(keyword),
                    FAQ.answer.like(keyword),
                    FAQ.category.like(keyword),
                ),
            ).order_by(FAQ.id)
        )
        return list(result.scalars().all())
