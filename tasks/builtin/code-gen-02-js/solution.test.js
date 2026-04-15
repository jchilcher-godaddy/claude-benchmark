const { analyzeText } = require('./solution');

test('empty string returns zeros', () => {
    const result = analyzeText('');
    expect(result.wordCount).toBe(0);
    expect(result.sentenceCount).toBe(0);
    expect(result.averageWordLength).toBe(0.0);
    expect(result.mostCommonWords).toEqual([]);
    expect(result.uniqueWordCount).toBe(0);
});

test('single word', () => {
    const result = analyzeText('hello');
    expect(result.wordCount).toBe(1);
    expect(result.sentenceCount).toBe(0);
    expect(result.averageWordLength).toBe(5.0);
    expect(result.mostCommonWords).toEqual([['hello', 1]]);
    expect(result.uniqueWordCount).toBe(1);
});

test('multiple sentences', () => {
    const result = analyzeText('Hello world! How are you? I am fine.');
    expect(result.wordCount).toBe(7);
    expect(result.sentenceCount).toBe(3);
    expect(result.averageWordLength).toBeCloseTo(3.29, 2);
});

test('case insensitive word counting', () => {
    const result = analyzeText('Hello hello HELLO');
    expect(result.uniqueWordCount).toBe(1);
    expect(result.mostCommonWords).toEqual([['hello', 3]]);
});

test('strips punctuation', () => {
    const result = analyzeText("it's a test, isn't it?");
    expect(result.uniqueWordCount).toBe(5);
    expect(result.wordCount).toBe(6);
});

test('most common words limited to 5', () => {
    const result = analyzeText('a b c d e f g h i j');
    expect(result.mostCommonWords.length).toBeLessThanOrEqual(5);
});

test('alphabetical tiebreaker', () => {
    const result = analyzeText('zebra apple banana');
    const words = result.mostCommonWords.map(([w, _]) => w);
    expect(words).toEqual(['apple', 'banana', 'zebra']);
});

test('handles repeated words', () => {
    const result = analyzeText('the the the cat cat dog');
    expect(result.mostCommonWords[0]).toEqual(['the', 3]);
    expect(result.mostCommonWords[1]).toEqual(['cat', 2]);
    expect(result.mostCommonWords[2]).toEqual(['dog', 1]);
});

test('whitespace only returns zeros', () => {
    const result = analyzeText('   \n\t  ');
    expect(result.wordCount).toBe(0);
    expect(result.uniqueWordCount).toBe(0);
});

test('complex text with multiple stats', () => {
    const text = 'The quick brown fox jumps over the lazy dog. The dog was not amused!';
    const result = analyzeText(text);
    expect(result.wordCount).toBe(14);
    expect(result.sentenceCount).toBe(2);
    expect(result.uniqueWordCount).toBe(12);
    expect(result.mostCommonWords[0]).toEqual(['the', 3]);
});
