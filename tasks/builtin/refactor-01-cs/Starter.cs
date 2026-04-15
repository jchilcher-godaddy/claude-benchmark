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
        double activeTotal = 0;
        foreach (var record in records)
        {
            if (record.Status == "active" && record.Amount > 0)
            {
                activeTotal += record.Amount;
            }
        }

        double highPriorityTotal = 0;
        foreach (var record in records)
        {
            if (record.Priority == "high" && record.Amount > 0)
            {
                highPriorityTotal += record.Amount;
            }
        }

        double pendingTotal = 0;
        foreach (var record in records)
        {
            if (record.Status == "pending" && record.Amount > 0)
            {
                pendingTotal += record.Amount;
            }
        }

        int activeHighPriorityCount = 0;
        foreach (var record in records)
        {
            if (record.Status == "active" && record.Priority == "high")
            {
                activeHighPriorityCount++;
            }
        }

        int pendingHighPriorityCount = 0;
        foreach (var record in records)
        {
            if (record.Status == "pending" && record.Priority == "high")
            {
                pendingHighPriorityCount++;
            }
        }

        return new ProcessResult
        {
            ActiveTotal = activeTotal,
            HighPriorityTotal = highPriorityTotal,
            PendingTotal = pendingTotal,
            ActiveHighPriorityCount = activeHighPriorityCount,
            PendingHighPriorityCount = pendingHighPriorityCount
        };
    }
}
