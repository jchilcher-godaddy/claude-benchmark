using Xunit;
using System.Collections.Generic;
using System.IO;
using System.Linq;

public class RecordProcessorTests
{
    [Fact]
    public void EmptyRecords()
    {
        var result = RecordProcessor.ProcessRecords(new List<Record>());
        Assert.Equal(0, result.ActiveTotal);
        Assert.Equal(0, result.HighPriorityTotal);
        Assert.Equal(0, result.PendingTotal);
        Assert.Equal(0, result.ActiveHighPriorityCount);
        Assert.Equal(0, result.PendingHighPriorityCount);
    }

    [Fact]
    public void SingleActiveRecord()
    {
        var records = new List<Record>
        {
            new Record { Status = "active", Amount = 100, Priority = "low" }
        };
        var result = RecordProcessor.ProcessRecords(records);
        Assert.Equal(100, result.ActiveTotal);
        Assert.Equal(0, result.HighPriorityTotal);
    }

    [Fact]
    public void HighPriorityRecords()
    {
        var records = new List<Record>
        {
            new Record { Status = "active", Amount = 50, Priority = "high" },
            new Record { Status = "pending", Amount = 75, Priority = "high" }
        };
        var result = RecordProcessor.ProcessRecords(records);
        Assert.Equal(125, result.HighPriorityTotal);
        Assert.Equal(1, result.ActiveHighPriorityCount);
        Assert.Equal(1, result.PendingHighPriorityCount);
    }

    [Fact]
    public void MixedRecords()
    {
        var records = new List<Record>
        {
            new Record { Status = "active", Amount = 100, Priority = "high" },
            new Record { Status = "pending", Amount = 200, Priority = "low" },
            new Record { Status = "active", Amount = 50, Priority = "low" },
            new Record { Status = "pending", Amount = 150, Priority = "high" }
        };

        var result = RecordProcessor.ProcessRecords(records);
        Assert.Equal(150, result.ActiveTotal);
        Assert.Equal(250, result.HighPriorityTotal);
        Assert.Equal(350, result.PendingTotal);
        Assert.Equal(1, result.ActiveHighPriorityCount);
        Assert.Equal(1, result.PendingHighPriorityCount);
    }

    [Fact]
    public void NegativeAmountsIgnored()
    {
        var records = new List<Record>
        {
            new Record { Status = "active", Amount = -50, Priority = "high" },
            new Record { Status = "active", Amount = 100, Priority = "high" }
        };
        var result = RecordProcessor.ProcessRecords(records);
        Assert.Equal(100, result.ActiveTotal);
    }

    [Fact]
    public void ZeroAmountsIgnored()
    {
        var records = new List<Record>
        {
            new Record { Status = "active", Amount = 0, Priority = "high" },
            new Record { Status = "active", Amount = 100, Priority = "high" }
        };
        var result = RecordProcessor.ProcessRecords(records);
        Assert.Equal(100, result.ActiveTotal);
    }

    [Fact]
    public void StructuralTest_NoLoops()
    {
        var solutionFile = "Solution.cs";
        if (!File.Exists(solutionFile))
        {
            Assert.Fail("Solution.cs not found");
            return;
        }

        var content = File.ReadAllText(solutionFile);
        var loopCount = System.Text.RegularExpressions.Regex.Matches(content, @"\bforeach\b|\bfor\b").Count;

        Assert.True(loopCount <= 2, $"Expected at most 2 loops in solution, found {loopCount}");
    }

    [Fact]
    public void StructuralTest_HasHelperMethods()
    {
        var solutionFile = "Solution.cs";
        if (!File.Exists(solutionFile))
        {
            Assert.Fail("Solution.cs not found");
            return;
        }

        var content = File.ReadAllText(solutionFile);
        var methodCount = System.Text.RegularExpressions.Regex.Matches(content, @"(private|public)\s+static\s+\w+\s+\w+\s*\(").Count;

        Assert.True(methodCount >= 2, "Expected helper methods to be extracted");
    }
}
