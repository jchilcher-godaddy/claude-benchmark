const { binarySearch } = require('./solution');

test('finds element in middle', () => {
    expect(binarySearch([1, 2, 3, 4, 5], 3)).toBe(2);
});

test('finds element at start', () => {
    expect(binarySearch([1, 2, 3, 4, 5], 1)).toBe(0);
});

test('finds element at end', () => {
    expect(binarySearch([1, 2, 3, 4, 5], 5)).toBe(4);
});

test('element not found', () => {
    expect(binarySearch([1, 2, 3, 4, 5], 6)).toBe(-1);
});

test('empty array', () => {
    expect(binarySearch([], 1)).toBe(-1);
});

test('single element found', () => {
    expect(binarySearch([5], 5)).toBe(0);
});

test('single element not found', () => {
    expect(binarySearch([5], 3)).toBe(-1);
});

test('two elements first', () => {
    expect(binarySearch([1, 2], 1)).toBe(0);
});

test('two elements second', () => {
    expect(binarySearch([1, 2], 2)).toBe(1);
});

test('two elements not found', () => {
    expect(binarySearch([1, 2], 3)).toBe(-1);
});

test('larger array', () => {
    const arr = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19];
    expect(binarySearch(arr, 7)).toBe(3);
    expect(binarySearch(arr, 15)).toBe(7);
    expect(binarySearch(arr, 1)).toBe(0);
    expect(binarySearch(arr, 19)).toBe(9);
});

test('not in larger array', () => {
    const arr = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19];
    expect(binarySearch(arr, 4)).toBe(-1);
    expect(binarySearch(arr, 20)).toBe(-1);
    expect(binarySearch(arr, 0)).toBe(-1);
});
