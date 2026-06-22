"""Database initialization script with sample data."""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import init_db, close_db, async_session_factory
from app.db.models import Order, FAQ
from app.db.repositories import OrderRepository, FAQRepository


SAMPLE_ORDERS = [
    Order(
        id="ORD-20240101-001",
        user_id="user-001",
        status="shipped",
        items=[{"name": "蓝牙耳机", "quantity": 1, "price": 299.00}],
        total_amount=299.00,
        tracking_number="SF1234567890",
    ),
    Order(
        id="ORD-20240102-002",
        user_id="user-001",
        status="pending",
        items=[{"name": "手机壳", "quantity": 2, "price": 29.00}],
        total_amount=58.00,
    ),
    Order(
        id="ORD-20240103-003",
        user_id="user-002",
        status="delivered",
        items=[{"name": "充电宝", "quantity": 1, "price": 159.00}],
        total_amount=159.00,
        tracking_number="YT9876543210",
    ),
]

SAMPLE_FAQS = [
    FAQ(
        question="如何查询订单状态？",
        answer="您可以通过提供订单号来查询订单状态。例如：帮我查一下订单 ORD-20240101-001 的状态。",
        category="订单查询",
        keywords=["订单", "查询", "状态", "物流"],
    ),
    FAQ(
        question="订单什么时候能到？",
        answer="普通快递一般3-5个工作日送达，顺丰快递1-2个工作日送达。具体时效以物流信息为准。",
        category="物流配送",
        keywords=["物流", "配送", "到货", "时效", "快递"],
    ),
    FAQ(
        question="可以退货吗？",
        answer="自商品签收之日起7天内，商品未使用且包装完好的情况下可以申请无理由退货。",
        category="退换货",
        keywords=["退货", "退款", "退换", "七天", "无理由"],
    ),
    FAQ(
        question="退款多久到账？",
        answer="退款审核通过后，一般1-3个工作日到账。具体到账时间取决于支付方式和银行处理速度。",
        category="退款",
        keywords=["退款", "到账", "时间", "多久"],
    ),
    FAQ(
        question="如何修改收货地址？",
        answer="订单未发货前可以修改收货地址。请联系客服提供订单号和新地址进行修改。",
        category="订单管理",
        keywords=["地址", "修改", "收货", "变更"],
    ),
    FAQ(
        question="发票怎么开？",
        answer="下单时可以选择开具电子发票，订单完成后会发送到您的邮箱。如需补开，请联系客服。",
        category="发票",
        keywords=["发票", "开具", "电子发票"],
    ),
    FAQ(
        question="会员有什么优惠？",
        answer="会员享受专属折扣、积分兑换、优先发货等权益。消费满1000元可升级为金牌会员。",
        category="会员",
        keywords=["会员", "优惠", "折扣", "积分", "权益"],
    ),
    FAQ(
        question="商品有质量问题怎么办？",
        answer="收到商品如有质量问题，请在7天内联系客服，提供照片凭证，我们会尽快为您处理退换货。",
        category="售后服务",
        keywords=["质量", "问题", "损坏", "售后"],
    ),
]


async def init_database():
    """Initialize database with sample data."""
    print("Initializing database...")

    # Initialize database connection
    await init_db()

    if not async_session_factory:
        print("ERROR: Database not configured. Set DATABASE_URL in .env")
        return

    async with async_session_factory() as session:
        # Check if data already exists
        order_repo = OrderRepository(session)
        existing_order = await order_repo.get_by_id("ORD-20240101-001")
        if existing_order:
            print("Database already initialized, skipping...")
            return

        # Insert sample orders
        print("Inserting sample orders...")
        for order in SAMPLE_ORDERS:
            session.add(order)

        # Insert sample FAQs
        print("Inserting sample FAQs...")
        for faq in SAMPLE_FAQS:
            session.add(faq)

        await session.commit()

    print("Database initialized successfully!")
    print(f"  - {len(SAMPLE_ORDERS)} orders")
    print(f"  - {len(SAMPLE_FAQS)} FAQs")

    await close_db()


if __name__ == "__main__":
    asyncio.run(init_database())
