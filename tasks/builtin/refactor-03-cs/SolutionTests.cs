using Xunit;
using System.IO;
using System.Linq;

public class DataProcessorTests
{
    [Fact]
    public void ValidInput()
    {
        var input = "apple,fruit,10.5\nbanana,fruit,8.25\ncarrot,vegetable,3.0";
        var result = DataProcessor.ProcessData(input);

        Assert.Contains("APPLE", result);
        Assert.Contains("BANANA", result);
        Assert.Contains("CARROT", result);
        Assert.Contains("15.75", result);
        Assert.Contains("12.38", result);
        Assert.Contains("4.50", result);
    }

    [Fact]
    public void EmptyInput()
    {
        var result = DataProcessor.ProcessData("");
        Assert.Contains("ERROR", result);
        Assert.Contains("No data", result);
    }

    [Fact]
    public void InvalidColumnCount()
    {
        var input = "apple,fruit\nbanana,fruit,8.25";
        var result = DataProcessor.ProcessData(input);
        Assert.Contains("ERROR", result);
        Assert.Contains("expected 3 columns", result);
    }

    [Fact]
    public void InvalidNumericValue()
    {
        var input = "apple,fruit,not-a-number";
        var result = DataProcessor.ProcessData(input);
        Assert.Contains("ERROR", result);
        Assert.Contains("not a valid number", result);
    }

    [Fact]
    public void SingleRow()
    {
        var input = "apple,fruit,10.0";
        var result = DataProcessor.ProcessData(input);

        Assert.Contains("APPLE", result);
        Assert.Contains("FRUIT", result);
        Assert.Contains("10.00", result);
        Assert.Contains("15.00", result);
    }

    [Fact]
    public void MultipleRows()
    {
        var input = "apple,fruit,10.0\nbanana,fruit,5.0\ncarrot,vegetable,2.5";
        var result = DataProcessor.ProcessData(input);

        var lines = result.Split('\n');
        Assert.Equal(3, lines.Length);
    }

    [Fact]
    public void WhitespaceHandling()
    {
        var input = " apple , fruit , 10.0 ";
        var result = DataProcessor.ProcessData(input);

        Assert.Contains("APPLE", result);
    }

    [Fact]
    public void StructuralTest_HasClasses()
    {
        var solutionFile = "Solution.cs";
        if (!File.Exists(solutionFile))
        {
            Assert.Fail("Solution.cs not found");
            return;
        }

        var content = File.ReadAllText(solutionFile);
        var classCount = System.Text.RegularExpressions.Regex.Matches(content, @"\bclass\s+\w+").Count;

        Assert.True(classCount >= 3, $"Expected at least 3 classes for separation of concerns, found {classCount}");
    }

    [Fact]
    public void StructuralTest_NoLongParameterChains()
    {
        var solutionFile = "Solution.cs";
        if (!File.Exists(solutionFile))
        {
            Assert.Fail("Solution.cs not found");
            return;
        }

        var content = File.ReadAllText(solutionFile);
        var methodMatches = System.Text.RegularExpressions.Regex.Matches(
            content,
            @"\b\w+\s+\w+\s*\([^)]{100,}\)"
        );

        Assert.True(methodMatches.Count <= 1, "Expected shorter parameter lists through use of instance attributes");
    }
}
