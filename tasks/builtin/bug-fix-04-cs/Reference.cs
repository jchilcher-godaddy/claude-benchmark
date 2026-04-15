using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

public class QueryBuilder
{
    private readonly string _table;
    private readonly List<string> _allowedColumns;
    private List<string> _columns = new() { "*" };
    private List<string> _whereClauses = new();
    private List<object> _whereParams = new();
    private string? _orderBy;

    public QueryBuilder(string table, List<string>? allowedColumns = null)
    {
        if (string.IsNullOrWhiteSpace(table))
            throw new ArgumentException("Table name cannot be empty", nameof(table));

        if (!IsValidIdentifier(table))
            throw new ArgumentException("Invalid table name", nameof(table));

        _table = table;
        _allowedColumns = allowedColumns ?? new List<string>();
    }

    public QueryBuilder Select(params string[] columns)
    {
        if (columns.Length > 0)
        {
            foreach (var col in columns)
            {
                if (col != "*" && !IsValidColumn(col))
                    throw new ArgumentException($"Invalid or disallowed column: {col}");
            }
            _columns = columns.ToList();
        }
        else
        {
            _columns = new List<string> { "*" };
        }
        return this;
    }

    public QueryBuilder Where(string condition, object? value = null)
    {
        if (value != null)
        {
            if (!IsValidIdentifier(condition))
                throw new ArgumentException("Invalid condition column name", nameof(condition));

            _whereClauses.Add($"{condition} = @p{_whereParams.Count}");
            _whereParams.Add(value);
        }
        else
        {
            _whereClauses.Add(condition);
        }
        return this;
    }

    public QueryBuilder OrderBy(string column, string direction = "ASC")
    {
        if (!IsValidColumn(column))
            throw new ArgumentException($"Invalid or disallowed column for ORDER BY: {column}");

        direction = direction.ToUpper();
        if (direction != "ASC" && direction != "DESC")
            throw new ArgumentException("Direction must be ASC or DESC", nameof(direction));

        _orderBy = $"{column} {direction}";
        return this;
    }

    public (string Sql, List<object> Parameters) Build()
    {
        var cols = string.Join(", ", _columns);
        var sql = $"SELECT {cols} FROM {_table}";

        if (_whereClauses.Any())
        {
            sql += " WHERE " + string.Join(" AND ", _whereClauses);
        }

        if (_orderBy != null)
        {
            sql += $" ORDER BY {_orderBy}";
        }

        return (sql, _whereParams);
    }

    private bool IsValidIdentifier(string identifier)
    {
        return Regex.IsMatch(identifier, @"^[a-zA-Z_][a-zA-Z0-9_]*$");
    }

    private bool IsValidColumn(string column)
    {
        if (column == "*") return true;
        if (!IsValidIdentifier(column)) return false;
        if (_allowedColumns.Any() && !_allowedColumns.Contains(column)) return false;
        return true;
    }
}
