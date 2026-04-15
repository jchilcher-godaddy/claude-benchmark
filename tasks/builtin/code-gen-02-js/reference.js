function analyzeText(text) {
    if (!text.trim()) {
        return {
            wordCount: 0,
            sentenceCount: 0,
            averageWordLength: 0.0,
            mostCommonWords: [],
            uniqueWordCount: 0
        };
    }

    const words = text.match(/[a-zA-Z]+/g) || [];
    const wordsLower = words.map(w => w.toLowerCase());

    const wordCount = words.length;
    const sentenceCount = (text.match(/[.!?]/g) || []).length;
    const averageWordLength = wordCount > 0
        ? parseFloat((words.reduce((sum, w) => sum + w.length, 0) / wordCount).toFixed(2))
        : 0.0;

    const counter = {};
    wordsLower.forEach(w => {
        counter[w] = (counter[w] || 0) + 1;
    });

    const entries = Object.entries(counter);
    entries.sort((a, b) => {
        if (b[1] !== a[1]) return b[1] - a[1];
        return a[0].localeCompare(b[0]);
    });
    const mostCommonWords = entries.slice(0, 5);

    const uniqueWordCount = Object.keys(counter).length;

    return {
        wordCount,
        sentenceCount,
        averageWordLength,
        mostCommonWords,
        uniqueWordCount
    };
}

module.exports = { analyzeText };
