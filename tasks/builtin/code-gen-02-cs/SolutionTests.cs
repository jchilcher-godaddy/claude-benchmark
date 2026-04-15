using Xunit;
using System.Linq;

public class TextAnalyzerTests
{
    [Fact]
    public void EmptyString()
    {
        var stats = TextAnalyzer.AnalyzeText("");
        Assert.Equal(0, stats.WordCount);
        Assert.Equal(0, stats.SentenceCount);
        Assert.Equal(0.0, stats.AverageWordLength);
        Assert.Empty(stats.MostCommonWords);
        Assert.Equal(0, stats.UniqueWordCount);
    }

    [Fact]
    public void SingleWord()
    {
        var stats = TextAnalyzer.AnalyzeText("Hello");
        Assert.Equal(1, stats.WordCount);
        Assert.Equal(0, stats.SentenceCount);
        Assert.Equal(5.0, stats.AverageWordLength);
        Assert.Single(stats.MostCommonWords);
        Assert.Equal(("hello", 1), stats.MostCommonWords[0]);
        Assert.Equal(1, stats.UniqueWordCount);
    }

    [Fact]
    public void SimpleSentence()
    {
        var stats = TextAnalyzer.AnalyzeText("Hello world!");
        Assert.Equal(2, stats.WordCount);
        Assert.Equal(1, stats.SentenceCount);
        Assert.Equal(5.0, stats.AverageWordLength);
        Assert.Equal(2, stats.UniqueWordCount);
    }

    [Fact]
    public void MultipleSentences()
    {
        var text = "The quick brown fox. Jumped over the lazy dog!";
        var stats = TextAnalyzer.AnalyzeText(text);
        Assert.Equal(9, stats.WordCount);
        Assert.Equal(2, stats.SentenceCount);
        Assert.Equal(2, stats.UniqueWordCount);
    }

    [Fact]
    public void CaseInsensitiveFrequency()
    {
        var text = "The the THE cat Cat";
        var stats = TextAnalyzer.AnalyzeText(text);
        Assert.Equal(5, stats.WordCount);
        Assert.Equal(2, stats.UniqueWordCount);
        Assert.Equal(("the", 3), stats.MostCommonWords[0]);
        Assert.Equal(("cat", 2), stats.MostCommonWords[1]);
    }

    [Fact]
    public void Top5MostCommon()
    {
        var text = "a a a b b c d e f g h";
        var stats = TextAnalyzer.AnalyzeText(text);
        Assert.Equal(5, stats.MostCommonWords.Count);
        Assert.Equal("a", stats.MostCommonWords[0].Word);
        Assert.Equal(3, stats.MostCommonWords[0].Count);
    }

    [Fact]
    public void AlphabeticalTieBreaking()
    {
        var text = "apple banana cherry date elderberry";
        var stats = TextAnalyzer.AnalyzeText(text);
        var words = stats.MostCommonWords.Select(x => x.Word).ToList();
        Assert.Equal(new[] { "apple", "banana", "cherry", "date", "elderberry" }, words);
    }

    [Fact]
    public void PunctuationStripping()
    {
        var text = "Hello, world! How's it going?";
        var stats = TextAnalyzer.AnalyzeText(text);
        Assert.Equal(5, stats.WordCount);
        Assert.Equal(2, stats.SentenceCount);
        Assert.True(stats.MostCommonWords.Any(x => x.Word == "hello"));
    }

    [Fact]
    public void AverageWordLengthRounding()
    {
        var text = "ab abc";
        var stats = TextAnalyzer.AnalyzeText(text);
        Assert.Equal(2.5, stats.AverageWordLength);
    }

    [Fact]
    public void WhitespaceOnly()
    {
        var stats = TextAnalyzer.AnalyzeText("   \t\n  ");
        Assert.Equal(0, stats.WordCount);
        Assert.Equal(0, stats.UniqueWordCount);
    }

    [Fact]
    public void ComplexText()
    {
        var text = "The quick brown fox jumps over the lazy dog. The dog was very lazy!";
        var stats = TextAnalyzer.AnalyzeText(text);
        Assert.Equal(14, stats.WordCount);
        Assert.Equal(2, stats.SentenceCount);
        Assert.True(stats.AverageWordLength > 0);
        Assert.True(stats.UniqueWordCount <= stats.WordCount);
        Assert.Equal("the", stats.MostCommonWords[0].Word);
        Assert.Equal(3, stats.MostCommonWords[0].Count);
    }
}
