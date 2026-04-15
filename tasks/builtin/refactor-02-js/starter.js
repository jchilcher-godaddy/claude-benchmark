function validateAndProcessOrder(order) {
    if (order.items !== undefined) {
        if (order.items.length > 0) {
            if (order.items.every(item => typeof item === 'object' && item !== null)) {
                if (order.items.every(item => 'price' in item && 'quantity' in item)) {
                    if (order.items.every(item => item.quantity > 0)) {
                        if (order.items.every(item => item.price >= 0)) {
                            const subtotal = order.items.reduce(
                                (sum, item) => sum + item.price * item.quantity,
                                0
                            );
                            let discount = 0;

                            if (order.customer_type !== undefined) {
                                if (order.customer_type === 'premium') {
                                    discount = subtotal * 0.15;
                                } else {
                                    if (order.customer_type === 'regular') {
                                        discount = subtotal * 0.05;
                                    }
                                }
                            }

                            if (order.coupon_code !== undefined) {
                                if (order.coupon_code === 'SAVE20') {
                                    const couponDiscount = subtotal * 0.20;
                                    if (couponDiscount > discount) {
                                        discount = couponDiscount;
                                    }
                                } else {
                                    if (order.coupon_code === 'SAVE10') {
                                        const couponDiscount = subtotal * 0.10;
                                        if (couponDiscount > discount) {
                                            discount = couponDiscount;
                                        }
                                    }
                                }
                            }

                            const total = subtotal - discount;

                            return {
                                valid: true,
                                subtotal,
                                discount,
                                total
                            };
                        } else {
                            return { valid: false, error: 'Item prices must be non-negative' };
                        }
                    } else {
                        return { valid: false, error: 'Item quantities must be positive' };
                    }
                } else {
                    return { valid: false, error: 'Items must have price and quantity' };
                }
            } else {
                return { valid: false, error: 'Items must be objects' };
            }
        } else {
            return { valid: false, error: 'Order must contain at least one item' };
        }
    } else {
        return { valid: false, error: 'Order must have items field' };
    }
}

module.exports = { validateAndProcessOrder };
