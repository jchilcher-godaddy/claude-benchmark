using System;
using System.Collections.Generic;
using System.Linq;

public class QueryBuilder
{
    private readonly string _table;
    private readonly List<string>? _allowedColumns;
    private List<string> _columns = new() { "*" };
    private string? _whereClause;
    private List<object> _whereParams = new();
    private string? _orderBy;

    public QueryBuilder(string table, List<string>? allowedColumns = null)
    {
        _table = table;
        _allowedColumns = allowedColumns;
    }

    public QueryBuilder Select(params string[] columns)
    {
        _columns = columns.Length > 0 ? columns.ToList() : new List<string> { "*" };
        return this;
    }

    public QueryBuilder Where(string condition, object? value = null)
    {
        if (value != null)
        {
            _whereClause = $"{condition} = '{value}'";
            _whereParams = new List<object>();
        }
        else
        {
            _whereClause = condition;
        }
        return this;
    }

    public QueryBuilder OrderBy(string column, string direction = "ASC")
    {
        _orderBy = $"{column} {direction}";
        return this;
    }

    public (string Sql, List<object> Parameters) Build()
    {
        var cols = string.Join(", ", _columns);
        var sql = $"SELECT {cols} FROM {_table}";

        var parameters = new List<object>();
        if (_whereClause != null)
        {
            sql += $" WHERE {_whereClause}";
            parameters = _whereParams;
        }

        if (_orderBy != null)
        {
            sql += $" ORDER BY {_orderBy}";
        }

        return (sql, parameters);
    }
}
