const { processRecords } = require('./solution');

test('empty records', () => {
    const result = processRecords([]);
    expect(result).toEqual({
        activeTotal: 0,
        highPriorityTotal: 0,
        pendingTotal: 0,
        activeHighPriorityCount: 0,
        pendingHighPriorityCount: 0
    });
});

test('single active record', () => {
    const records = [{ status: 'active', amount: 100, priority: 'low' }];
    const result = processRecords(records);
    expect(result.activeTotal).toBe(100);
    expect(result.highPriorityTotal).toBe(0);
    expect(result.pendingTotal).toBe(0);
});

test('single high priority record', () => {
    const records = [{ status: 'active', amount: 50, priority: 'high' }];
    const result = processRecords(records);
    expect(result.highPriorityTotal).toBe(50);
    expect(result.activeHighPriorityCount).toBe(1);
});

test('mixed records', () => {
    const records = [
        { status: 'active', amount: 100, priority: 'high' },
        { status: 'pending', amount: 50, priority: 'high' },
        { status: 'active', amount: 75, priority: 'low' }
    ];
    const result = processRecords(records);
    expect(result.activeTotal).toBe(175);
    expect(result.highPriorityTotal).toBe(150);
    expect(result.pendingTotal).toBe(50);
    expect(result.activeHighPriorityCount).toBe(1);
    expect(result.pendingHighPriorityCount).toBe(1);
});

test('ignores negative amounts', () => {
    const records = [
        { status: 'active', amount: -100, priority: 'low' },
        { status: 'active', amount: 50, priority: 'low' }
    ];
    const result = processRecords(records);
    expect(result.activeTotal).toBe(50);
});

test('ignores zero amounts', () => {
    const records = [
        { status: 'active', amount: 0, priority: 'low' },
        { status: 'active', amount: 50, priority: 'low' }
    ];
    const result = processRecords(records);
    expect(result.activeTotal).toBe(50);
});

test('handles missing fields', () => {
    const records = [
        { status: 'active' },
        { amount: 100 },
        { priority: 'high' }
    ];
    const result = processRecords(records);
    expect(result.activeTotal).toBe(0);
    expect(result.highPriorityTotal).toBe(0);
});

test('counts correctly', () => {
    const records = [
        { status: 'active', priority: 'high', amount: 10 },
        { status: 'active', priority: 'high', amount: 20 },
        { status: 'pending', priority: 'high', amount: 30 }
    ];
    const result = processRecords(records);
    expect(result.activeHighPriorityCount).toBe(2);
    expect(result.pendingHighPriorityCount).toBe(1);
});

test('structural quality check', () => {
    const fs = require('fs');
    const path = require('path');
    const filePath = path.join(__dirname, 'solution.js');
    const content = fs.readFileSync(filePath, 'utf8');

    const forLoopCount = (content.match(/for\s*\(/g) || []).length;
    expect(forLoopCount).toBeLessThanOrEqual(2);
});
