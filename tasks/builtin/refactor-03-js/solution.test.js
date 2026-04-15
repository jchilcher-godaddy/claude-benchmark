const { processData } = require('./solution');

test('valid data processing', () => {
    const input = 'apple,fruit,10\nbanana,fruit,5\ncarrot,vegetable,3';
    const result = processData(input);
    expect(result).toContain('APPLE');
    expect(result).toContain('FRUIT');
    expect(result).toContain('10.00');
    expect(result).toContain('15.00');
});

test('empty input returns error', () => {
    const result = processData('');
    expect(result).toBe('ERROR: No data');
});

test('wrong column count', () => {
    const input = 'apple,fruit\nbanana,fruit,5';
    const result = processData(input);
    expect(result).toMatch(/ERROR.*expected 3 columns/);
});

test('invalid numeric value', () => {
    const input = 'apple,fruit,notanumber';
    const result = processData(input);
    expect(result).toMatch(/ERROR.*not a valid number/);
});

test('text normalization', () => {
    const input = 'apple,fruit,10';
    const result = processData(input);
    expect(result).toContain('APPLE');
    expect(result).toContain('FRUIT');
});

test('computed column', () => {
    const input = 'apple,fruit,10';
    const result = processData(input);
    expect(result).toContain('15.00');
});

test('multiple rows', () => {
    const input = 'apple,fruit,10\nbanana,fruit,5\ncarrot,vegetable,3';
    const result = processData(input);
    const lines = result.split('\n');
    expect(lines.length).toBe(3);
});

test('formatting with pipes', () => {
    const input = 'apple,fruit,10';
    const result = processData(input);
    expect(result).toContain(' | ');
});

test('numeric formatting', () => {
    const input = 'apple,fruit,10.5';
    const result = processData(input);
    expect(result).toContain('10.50');
    expect(result).toContain('15.75');
});

test('handles whitespace in cells', () => {
    const input = ' apple , fruit , 10 ';
    const result = processData(input);
    expect(result).toContain('APPLE');
    expect(result).toContain('FRUIT');
    expect(result).toContain('10.00');
});

test('skips blank lines', () => {
    const input = 'apple,fruit,10\n\nbanana,fruit,5';
    const result = processData(input);
    const lines = result.split('\n');
    expect(lines.length).toBe(2);
});

test('structural quality check', () => {
    const fs = require('fs');
    const path = require('path');
    const filePath = path.join(__dirname, 'solution.js');
    const content = fs.readFileSync(filePath, 'utf8');

    const classCount = (content.match(/class\s+\w+/g) || []).length;
    expect(classCount).toBeGreaterThanOrEqual(3);
});
