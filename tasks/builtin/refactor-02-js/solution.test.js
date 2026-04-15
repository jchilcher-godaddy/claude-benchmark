const { validateAndProcessOrder } = require('./solution');

test('valid order basic', () => {
    const order = {
        items: [{ price: 10, quantity: 2 }]
    };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(true);
    expect(result.subtotal).toBe(20);
    expect(result.total).toBe(20);
});

test('missing items field', () => {
    const order = {};
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/items field/i);
});

test('empty items array', () => {
    const order = { items: [] };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/at least one item/i);
});

test('items not objects', () => {
    const order = { items: ['invalid'] };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/objects/i);
});

test('missing price or quantity', () => {
    const order = { items: [{ price: 10 }] };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/price and quantity/i);
});

test('negative quantity', () => {
    const order = { items: [{ price: 10, quantity: -1 }] };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/quantities must be positive/i);
});

test('negative price', () => {
    const order = { items: [{ price: -10, quantity: 1 }] };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/prices must be non-negative/i);
});

test('premium discount', () => {
    const order = {
        items: [{ price: 100, quantity: 1 }],
        customer_type: 'premium'
    };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(true);
    expect(result.discount).toBe(15);
    expect(result.total).toBe(85);
});

test('regular discount', () => {
    const order = {
        items: [{ price: 100, quantity: 1 }],
        customer_type: 'regular'
    };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(true);
    expect(result.discount).toBe(5);
    expect(result.total).toBe(95);
});

test('SAVE20 coupon', () => {
    const order = {
        items: [{ price: 100, quantity: 1 }],
        coupon_code: 'SAVE20'
    };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(true);
    expect(result.discount).toBe(20);
    expect(result.total).toBe(80);
});

test('SAVE10 coupon', () => {
    const order = {
        items: [{ price: 100, quantity: 1 }],
        coupon_code: 'SAVE10'
    };
    const result = validateAndProcessOrder(order);
    expect(result.valid).toBe(true);
    expect(result.discount).toBe(10);
    expect(result.total).toBe(90);
});

test('coupon overrides customer discount', () => {
    const order = {
        items: [{ price: 100, quantity: 1 }],
        customer_type: 'regular',
        coupon_code: 'SAVE20'
    };
    const result = validateAndProcessOrder(order);
    expect(result.discount).toBe(20);
    expect(result.total).toBe(80);
});

test('customer discount used if coupon smaller', () => {
    const order = {
        items: [{ price: 100, quantity: 1 }],
        customer_type: 'premium',
        coupon_code: 'SAVE10'
    };
    const result = validateAndProcessOrder(order);
    expect(result.discount).toBe(15);
    expect(result.total).toBe(85);
});

test('multiple items', () => {
    const order = {
        items: [
            { price: 50, quantity: 2 },
            { price: 30, quantity: 1 }
        ]
    };
    const result = validateAndProcessOrder(order);
    expect(result.subtotal).toBe(130);
});
