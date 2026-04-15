const { AsyncCounter } = require('./solution');

test('single increment', async () => {
    const counter = new AsyncCounter();
    await counter.increment();
    expect(counter.get()).toBe(1);
});

test('multiple sequential increments', async () => {
    const counter = new AsyncCounter();
    await counter.increment();
    await counter.increment();
    await counter.increment();
    expect(counter.get()).toBe(3);
});

test('concurrent increments', async () => {
    const counter = new AsyncCounter();
    await Promise.all([
        counter.increment(),
        counter.increment(),
        counter.increment(),
        counter.increment(),
        counter.increment()
    ]);
    expect(counter.get()).toBe(5);
});

test('many concurrent increments', async () => {
    const counter = new AsyncCounter();
    const promises = [];
    for (let i = 0; i < 50; i++) {
        promises.push(counter.increment());
    }
    await Promise.all(promises);
    expect(counter.get()).toBe(50);
});

test('decrement', async () => {
    const counter = new AsyncCounter();
    await counter.increment();
    await counter.increment();
    await counter.decrement();
    expect(counter.get()).toBe(1);
});

test('concurrent increments and decrements', async () => {
    const counter = new AsyncCounter();
    await Promise.all([
        counter.increment(),
        counter.increment(),
        counter.increment(),
        counter.decrement(),
        counter.increment(),
        counter.decrement()
    ]);
    expect(counter.get()).toBe(2);
});

test('reset', async () => {
    const counter = new AsyncCounter();
    await counter.increment();
    await counter.increment();
    counter.reset();
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(counter.get()).toBe(0);
});

test('incrementBy', async () => {
    const counter = new AsyncCounter();
    await counter.incrementBy(5);
    expect(counter.get()).toBe(5);
});

test('concurrent incrementBy', async () => {
    const counter = new AsyncCounter();
    await Promise.all([
        counter.incrementBy(5),
        counter.incrementBy(3),
        counter.incrementBy(2)
    ]);
    expect(counter.get()).toBe(10);
});

test('mixed operations', async () => {
    const counter = new AsyncCounter();
    await Promise.all([
        counter.increment(),
        counter.incrementBy(5),
        counter.increment(),
        counter.decrement(),
        counter.incrementBy(3)
    ]);
    expect(counter.get()).toBe(9);
});

test('stress test', async () => {
    const counter = new AsyncCounter();
    const promises = [];
    for (let i = 0; i < 100; i++) {
        promises.push(counter.increment());
    }
    for (let i = 0; i < 20; i++) {
        promises.push(counter.decrement());
    }
    await Promise.all(promises);
    expect(counter.get()).toBe(80);
});
