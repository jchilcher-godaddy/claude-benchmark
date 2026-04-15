using System;
using System.Collections.Generic;
using System.Linq;

public class ProcessResult
{
    public double ActiveTotal { get; set; }
    public double HighPriorityTotal { get; set; }
    public double PendingTotal { get; set; }
    public int ActiveHighPriorityCount { get; set; }
    public int PendingHighPriorityCount { get; set; }
}

public class Record
{
    public string? Status { get; set; }
    public double Amount { get; set; }
    public string? Priority { get; set; }
}

public static class RecordProcessor
{
    public static ProcessResult ProcessRecords(List<Record> records)
    {
        return new ProcessResult
        {
            ActiveTotal = SumAmounts(records, r => r.Status == "active"),
            HighPriorityTotal = SumAmounts(records, r => r.Priority == "high"),
            PendingTotal = SumAmounts(records, r => r.Status == "pending"),
            ActiveHighPriorityCount = CountRecords(records, r => r.Status == "active" && r.Priority == "high"),
            PendingHighPriorityCount = CountRecords(records, r => r.Status == "pending" && r.Priority == "high")
        };
    }

    private static double SumAmounts(List<Record> records, Func<Record, bool> predicate)
    {
        return records
            .Where(predicate)
            .Where(r => r.Amount > 0)
            .Sum(r => r.Amount);
    }

    private static int CountRecords(List<Record> records, Func<Record, bool> predicate)
    {
        return records.Count(predicate);
    }
}
