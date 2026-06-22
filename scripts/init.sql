-- LingXi Service Database Initialization Script
-- This script runs when the MySQL container starts for the first time

USE lingxi;

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    items JSON,
    total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    tracking_number VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create return_orders table
CREATE TABLE IF NOT EXISTS return_orders (
    id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'refund',
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_order_id (order_id),
    INDEX idx_user_id (user_id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create faqs table
CREATE TABLE IF NOT EXISTS faqs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category VARCHAR(50),
    keywords JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert sample orders
INSERT INTO orders (id, user_id, status, items, total_amount, tracking_number) VALUES
('ORD-20240101-001', 'user-001', 'shipped', '[{"name": "蓝牙耳机", "quantity": 1, "price": 299.00}]', 299.00, 'SF1234567890'),
('ORD-20240102-002', 'user-001', 'pending', '[{"name": "手机壳", "quantity": 2, "price": 29.00}]', 58.00, NULL),
('ORD-20240103-003', 'user-002', 'delivered', '[{"name": "充电宝", "quantity": 1, "price": 159.00}]', 159.00, 'YT9876543210')
ON DUPLICATE KEY UPDATE status=VALUES(status);

-- Insert sample FAQs
INSERT INTO faqs (question, answer, category, keywords) VALUES
('如何查询订单状态？', '您可以通过提供订单号来查询订单状态。例如：帮我查一下订单 ORD-20240101-001 的状态。', '订单查询', '["订单", "查询", "状态", "物流"]'),
('订单什么时候能到？', '普通快递一般3-5个工作日送达，顺丰快递1-2个工作日送达。具体时效以物流信息为准。', '物流配送', '["物流", "配送", "到货", "时效", "快递"]'),
('可以退货吗？', '自商品签收之日起7天内，商品未使用且包装完好的情况下可以申请无理由退货。', '退换货', '["退货", "退款", "退换", "七天", "无理由"]'),
('退款多久到账？', '退款审核通过后，一般1-3个工作日到账。具体到账时间取决于支付方式和银行处理速度。', '退款', '["退款", "到账", "时间", "多久"]'),
('如何修改收货地址？', '订单未发货前可以修改收货地址。请联系客服提供订单号和新地址进行修改。', '订单管理', '["地址", "修改", "收货", "变更"]'),
('发票怎么开？', '下单时可以选择开具电子发票，订单完成后会发送到您的邮箱。如需补开，请联系客服。', '发票', '["发票", "开具", "电子发票"]'),
('会员有什么优惠？', '会员享受专属折扣、积分兑换、优先发货等权益。消费满1000元可升级为金牌会员。', '会员', '["会员", "优惠", "折扣", "积分", "权益"]'),
('商品有质量问题怎么办？', '收到商品如有质量问题，请在7天内联系客服，提供照片凭证，我们会尽快为您处理退换货。', '售后服务', '["质量", "问题", "损坏", "售后"]');
