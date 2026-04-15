const { mergeSort } = require('./solution');

test('empty array', () => {
    expect(mergeSort([])).toEqual([]);
});

test('single element', () => {
    expect(mergeSort([5])).toEqual([5]);
});

test('already sorted', () => {
    expect(mergeSort([1, 2, 3, 4, 5])).toEqual([1, 2, 3, 4, 5]);
});

test('reverse sorted', () => {
    expect(mergeSort([5, 4, 3, 2, 1])).toEqual([1, 2, 3, 4, 5]);
});

test('random order', () => {
    expect(mergeSort([3, 1, 4, 1, 5, 9, 2, 6])).toEqual([1, 1, 2, 3, 4, 5, 6, 9]);
});

test('duplicates', () => {
    expect(mergeSort([3, 3, 3, 1, 1, 2])).toEqual([1, 1, 2, 3, 3, 3]);
});

test('does not modify original', () => {
    const original = [3, 1, 2];
    const sorted = mergeSort(original);
    expect(original).toEqual([3, 1, 2]);
    expect(sorted).toEqual([1, 2, 3]);
});

test('stability with objects', () => {
    const arr = [
        { val: 3, id: 'a' },
        { val: 1, id: 'b' },
        { val: 3, id: 'c' },
        { val: 1, id: 'd' }
    ];
    const sorted = mergeSort(arr);
    expect(sorted[0].id).toBe('b');
    expect(sorted[1].id).toBe('d');
    expect(sorted[2].id).toBe('a');
    expect(sorted[3].id).toBe('c');
});

test('two elements', () => {
    expect(mergeSort([2, 1])).toEqual([1, 2]);
});

test('negative numbers', () => {
    expect(mergeSort([-3, -1, -2, 0, 1])).toEqual([-3, -2, -1, 0, 1]);
});

test('large array', () => {
    const arr = Array.from({ length: 100 }, () => Math.floor(Math.random() * 100));
    const sorted = mergeSort(arr);
    for (let i = 1; i < sorted.length; i++) {
        expect(sorted[i]).toBeGreaterThanOrEqual(sorted[i - 1]);
    }
});
