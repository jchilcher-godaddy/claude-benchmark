using System;
using System.Collections.Generic;
using System.Linq;

public static class DataProcessor
{
    public static string ProcessData(string rawInput)
    {
        var rows = ParseLines(rawInput);
        if (rows.Count == 0)
            return "ERROR: No data";

        var (validRows, validationErrors) = ValidateRows(rows, 3);
        if (validationErrors.Any())
            return "ERROR: " + string.Join("; ", validationErrors);

        var (parsedRows, parseErrors) = ParseNumericColumns(validRows, new HashSet<int> { 2 });
        if (parseErrors.Any())
            return "ERROR: " + string.Join("; ", parseErrors);

        var normalizedRows = NormalizeTextColumns(parsedRows, new HashSet<int> { 0, 1 });
        var computedRows = ComputeDerivedColumn(normalizedRows, 2, 1.5);
        var result = FormatRowsAsTable(computedRows, new[] { 15, 12, 10, 10 });

        return result;
    }

    private static List<List<string>> ParseLines(string rawInput)
    {
        var lines = rawInput.Trim().Split('\n');
        var rows = new List<List<string>>();
        foreach (var line in lines)
        {
            if (!string.IsNullOrWhiteSpace(line))
            {
                var parts = line.Split(',').ToList();
                rows.Add(parts);
            }
        }
        return rows;
    }

    private static (List<List<string>> ValidRows, List<string> Errors) ValidateRows(
        List<List<string>> rows, int expectedColumns)
    {
        var validRows = new List<List<string>>();
        var errors = new List<string>();
        for (int i = 0; i < rows.Count; i++)
        {
            if (rows[i].Count != expectedColumns)
            {
                errors.Add($"Row {i}: expected {expectedColumns} columns, got {rows[i].Count}");
            }
            else
            {
                validRows.Add(rows[i]);
            }
        }
        return (validRows, errors);
    }

    private static (List<List<object>> ParsedRows, List<string> Errors) ParseNumericColumns(
        List<List<string>> rows, HashSet<int> columnIndices)
    {
        var parsedRows = new List<List<object>>();
        var errors = new List<string>();
        for (int i = 0; i < rows.Count; i++)
        {
            var parsedRow = new List<object>();
            bool hasError = false;
            for (int j = 0; j < rows[i].Count; j++)
            {
                if (columnIndices.Contains(j))
                {
                    if (double.TryParse(rows[i][j].Trim(), out double value))
                    {
                        parsedRow.Add(value);
                    }
                    else
                    {
                        errors.Add($"Row {i}, column {j}: '{rows[i][j]}' is not a valid number");
                        hasError = true;
                        break;
                    }
                }
                else
                {
                    parsedRow.Add(rows[i][j].Trim());
                }
            }
            if (!hasError)
            {
                parsedRows.Add(parsedRow);
            }
        }
        return (parsedRows, errors);
    }

    private static List<List<object>> NormalizeTextColumns(
        List<List<object>> rows, HashSet<int> columnIndices)
    {
        var normalizedRows = new List<List<object>>();
        foreach (var row in rows)
        {
            var normalizedRow = new List<object>();
            for (int j = 0; j < row.Count; j++)
            {
                if (columnIndices.Contains(j) && row[j] is string str)
                {
                    normalizedRow.Add(str.ToUpper());
                }
                else
                {
                    normalizedRow.Add(row[j]);
                }
            }
            normalizedRows.Add(normalizedRow);
        }
        return normalizedRows;
    }

    private static List<List<object>> ComputeDerivedColumn(
        List<List<object>> rows, int sourceColIdx, double multiplier)
    {
        var resultRows = new List<List<object>>();
        foreach (var row in rows)
        {
            var newRow = new List<object>(row);
            newRow.Add((double)row[sourceColIdx] * multiplier);
            resultRows.Add(newRow);
        }
        return resultRows;
    }

    private static string FormatRowsAsTable(List<List<object>> rows, int[] columnWidths)
    {
        var lines = new List<string>();
        foreach (var row in rows)
        {
            var formattedCells = new List<string>();
            for (int i = 0; i < row.Count; i++)
            {
                int width = columnWidths[i];
                if (row[i] is double d)
                {
                    formattedCells.Add(d.ToString($"F2").PadLeft(width));
                }
                else
                {
                    formattedCells.Add(row[i].ToString()!.PadRight(width));
                }
            }
            lines.Add(string.Join(" | ", formattedCells));
        }
        return string.Join("\n", lines);
    }
}
