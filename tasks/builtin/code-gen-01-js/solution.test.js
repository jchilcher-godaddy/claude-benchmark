const { fibonacci } = require('./solution');

test('base case zero', () => {
    expect(fibonacci(0)).toBe(0);
});

test('base case one', () => {
    expect(fibonacci(1)).toBe(1);
});

test('small fibonacci', () => {
    expect(fibonacci(10)).toBe(55);
});

test('larger fibonacci', () => {
    expect(fibonacci(20)).toBe(6765);
});

test('negative throws error', () => {
    expect(() => fibonacci(-1)).toThrow();
});

test('large fibonacci', () => {
    expect(fibonacci(50)).toBe(12586269025);
});

test('sequence consistency', () => {
    for (let n = 2; n < 15; n++) {
        expect(fibonacci(n)).toBe(fibonacci(n - 1) + fibonacci(n - 2));
    }
});

test('small values', () => {
    expect(fibonacci(2)).toBe(1);
    expect(fibonacci(3)).toBe(2);
    expect(fibonacci(4)).toBe(3);
    expect(fibonacci(5)).toBe(5);
    expect(fibonacci(6)).toBe(8);
    expect(fibonacci(7)).toBe(13);
});

test('very large efficient', () => {
    expect(fibonacci(70)).toBe(190392490709135);
});

test('negative various', () => {
    expect(() => fibonacci(-5)).toThrow();
    expect(() => fibonacci(-100)).toThrow();
});

test('fibonacci 30', () => {
    expect(fibonacci(30)).toBe(832040);
});

test('return type is number', () => {
    expect(typeof fibonacci(10)).toBe('number');
});
