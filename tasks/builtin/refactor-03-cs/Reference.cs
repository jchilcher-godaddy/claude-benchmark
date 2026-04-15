using System;
using System.Collections.Generic;
using System.Linq;

public class CsvParser
{
    public List<List<string>> Parse(string rawInput)
    {
        var lines = rawInput.Trim().Split('\n');
        var rows = new List<List<string>>();
        foreach (var line in lines)
        {
            if (!string.IsNullOrWhiteSpace(line))
            {
                var parts = line.Split(',').Select(p => p.Trim()).ToList();
                rows.Add(parts);
            }
        }
        return rows;
    }
}

public class DataValidator
{
    private readonly int _expectedColumns;

    public DataValidator(int expectedColumns)
    {
        _expectedColumns = expectedColumns;
    }

    public (List<List<string>> ValidRows, List<string> Errors) Validate(List<List<string>> rows)
    {
        var validRows = new List<List<string>>();
        var errors = new List<string>();
        for (int i = 0; i < rows.Count; i++)
        {
            if (rows[i].Count != _expectedColumns)
            {
                errors.Add($"Row {i}: expected {_expectedColumns} columns, got {rows[i].Count}");
            }
            else
            {
                validRows.Add(rows[i]);
            }
        }
        return (validRows, errors);
    }
}

public class DataTransformer
{
    private readonly HashSet<int> _numericColumns;
    private readonly HashSet<int> _textColumns;

    public DataTransformer(HashSet<int> numericColumns, HashSet<int> textColumns)
    {
        _numericColumns = numericColumns;
        _textColumns = textColumns;
    }

    public (List<List<object>> ParsedRows, List<string> Errors) ParseNumericColumns(List<List<string>> rows)
    {
        var parsedRows = new List<List<object>>();
        var errors = new List<string>();

        for (int i = 0; i < rows.Count; i++)
        {
            var parsedRow = new List<object>();
            bool hasError = false;

            for (int j = 0; j < rows[i].Count; j++)
            {
                if (_numericColumns.Contains(j))
                {
                    if (double.TryParse(rows[i][j], out double value))
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
                    parsedRow.Add(rows[i][j]);
                }
            }

            if (!hasError)
                parsedRows.Add(parsedRow);
        }

        return (parsedRows, errors);
    }

    public List<List<object>> NormalizeTextColumns(List<List<object>> rows)
    {
        var normalizedRows = new List<List<object>>();
        foreach (var row in rows)
        {
            var normalizedRow = new List<object>();
            for (int j = 0; j < row.Count; j++)
            {
                if (_textColumns.Contains(j) && row[j] is string str)
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

    public List<List<object>> AddDerivedColumn(List<List<object>> rows, int sourceColIdx, double multiplier)
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
}

public class TableFormatter
{
    private readonly int[] _columnWidths;

    public TableFormatter(int[] columnWidths)
    {
        _columnWidths = columnWidths;
    }

    public string Format(List<List<object>> rows)
    {
        var lines = new List<string>();
        foreach (var row in rows)
        {
            var formattedCells = new List<string>();
            for (int i = 0; i < row.Count; i++)
            {
                int width = _columnWidths[i];
                if (row[i] is double d)
                {
                    formattedCells.Add(d.ToString("F2").PadLeft(width));
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

public static class DataProcessor
{
    public static string ProcessData(string rawInput)
    {
        var parser = new CsvParser();
        var rows = parser.Parse(rawInput);

        if (rows.Count == 0)
            return "ERROR: No data";

        var validator = new DataValidator(3);
        var (validRows, validationErrors) = validator.Validate(rows);
        if (validationErrors.Any())
            return "ERROR: " + string.Join("; ", validationErrors);

        var transformer = new DataTransformer(
            new HashSet<int> { 2 },
            new HashSet<int> { 0, 1 }
        );

        var (parsedRows, parseErrors) = transformer.ParseNumericColumns(validRows);
        if (parseErrors.Any())
            return "ERROR: " + string.Join("; ", parseErrors);

        var normalizedRows = transformer.NormalizeTextColumns(parsedRows);
        var computedRows = transformer.AddDerivedColumn(normalizedRows, 2, 1.5);

        var formatter = new TableFormatter(new[] { 15, 12, 10, 10 });
        return formatter.Format(computedRows);
    }
}
