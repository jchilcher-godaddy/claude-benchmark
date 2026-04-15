function validateAndProcessOrder(order) {
    if (order.items === undefined) {
        return { valid: false, error: 'Order must have items field' };
    }

    if (order.items.length === 0) {
        return { valid: false, error: 'Order must contain at least one item' };
    }

    if (!order.items.every(item => typeof item === 'object' && item !== null)) {
        return { valid: false, error: 'Items must be objects' };
    }

    if (!order.items.every(item => 'price' in item && 'quantity' in item)) {
        return { valid: false, error: 'Items must have price and quantity' };
    }

    if (!order.items.every(item => item.quantity > 0)) {
        return { valid: false, error: 'Item quantities must be positive' };
    }

    if (!order.items.every(item => item.price >= 0)) {
        return { valid: false, error: 'Item prices must be non-negative' };
    }

    const subtotal = order.items.reduce(
        (sum, item) => sum + item.price * item.quantity,
        0
    );
    let discount = 0;

    if (order.customer_type !== undefined) {
        if (order.customer_type === 'premium') {
            discount = subtotal * 0.15;
        } else if (order.customer_type === 'regular') {
            discount = subtotal * 0.05;
        }
    }

    if (order.coupon_code !== undefined) {
        let couponDiscount = 0;
        if (order.coupon_code === 'SAVE20') {
            couponDiscount = subtotal * 0.20;
        } else if (order.coupon_code === 'SAVE10') {
            couponDiscount = subtotal * 0.10;
        }

        if (couponDiscount > discount) {
            discount = couponDiscount;
        }
    }

    const total = subtotal - discount;

    return {
        valid: true,
        subtotal,
        discount,
        total
    };
}

module.exports = { validateAndProcessOrder };
