using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

public class TextStats
{
    public int WordCount { get; set; }
    public int SentenceCount { get; set; }
    public double AverageWordLength { get; set; }
    public List<(string Word, int Count)> MostCommonWords { get; set; } = new();
    public int UniqueWordCount { get; set; }
}

public static class TextAnalyzer
{
    public static TextStats AnalyzeText(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return new TextStats
            {
                WordCount = 0,
                SentenceCount = 0,
                AverageWordLength = 0.0,
                MostCommonWords = new List<(string, int)>(),
                UniqueWordCount = 0
            };
        }

        var words = Regex.Matches(text, @"[a-zA-Z]+")
            .Select(m => m.Value)
            .ToList();

        var wordsLower = words.Select(w => w.ToLower()).ToList();

        int wordCount = words.Count;
        int sentenceCount = Regex.Matches(text, @"[.!?]").Count;
        double averageWordLength = wordCount > 0
            ? Math.Round(words.Sum(w => w.Length) / (double)wordCount, 2)
            : 0.0;

        var wordFrequency = wordsLower
            .GroupBy(w => w)
            .Select(g => (Word: g.Key, Count: g.Count()))
            .OrderByDescending(x => x.Count)
            .ThenBy(x => x.Word)
            .Take(5)
            .ToList();

        int uniqueWordCount = wordsLower.Distinct().Count();

        return new TextStats
        {
            WordCount = wordCount,
            SentenceCount = sentenceCount,
            AverageWordLength = averageWordLength,
            MostCommonWords = wordFrequency,
            UniqueWordCount = uniqueWordCount
        };
    }
}
