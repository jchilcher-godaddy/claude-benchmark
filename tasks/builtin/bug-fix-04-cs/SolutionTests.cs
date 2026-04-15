using Xunit;
using System;
using System.Collections.Generic;

public class QueryBuilderTests
{
    [Fact]
    public void BasicSelectAll()
    {
        var qb = new QueryBuilder("users");
        var (sql, parameters) = qb.Build();

        Assert.Equal("SELECT * FROM users", sql);
        Assert.Empty(parameters);
    }

    [Fact]
    public void SelectSpecificColumns()
    {
        var qb = new QueryBuilder("users");
        var (sql, parameters) = qb.Select("id", "name").Build();

        Assert.Equal("SELECT id, name FROM users", sql);
        Assert.Empty(parameters);
    }

    [Fact]
    public void WhereWithValue()
    {
        var qb = new QueryBuilder("users");
        var (sql, parameters) = qb.Where("id", 42).Build();

        Assert.Equal("SELECT * FROM users WHERE id = @p0", sql);
        Assert.Single(parameters);
        Assert.Equal(42, parameters[0]);
    }

    [Fact]
    public void MultipleWhereChained()
    {
        var qb = new QueryBuilder("users");
        var (sql, parameters) = qb
            .Where("status", "active")
            .Where("age", 25)
            .Build();

        Assert.Contains("AND", sql);
        Assert.Equal(2, parameters.Count);
    }

    [Fact]
    public void OrderByColumn()
    {
        var qb = new QueryBuilder("users", new List<string> { "name" });
        var (sql, _) = qb.OrderBy("name", "DESC").Build();

        Assert.Contains("ORDER BY name DESC", sql);
    }

    [Fact]
    public void InvalidTableNameThrows()
    {
        Assert.Throws<ArgumentException>(() => new QueryBuilder("users; DROP TABLE users"));
    }

    [Fact]
    public void InvalidColumnInOrderByThrows()
    {
        var qb = new QueryBuilder("users", new List<string> { "id", "name" });
        Assert.Throws<ArgumentException>(() => qb.OrderBy("name; DROP TABLE users"));
    }

    [Fact]
    public void DisallowedColumnThrows()
    {
        var qb = new QueryBuilder("users", new List<string> { "id", "name" });
        Assert.Throws<ArgumentException>(() => qb.Select("password"));
    }

    [Fact]
    public void AllowedColumnsEnforced()
    {
        var qb = new QueryBuilder("users", new List<string> { "id", "name" });
        var (sql, _) = qb.Select("id", "name").Build();

        Assert.Contains("id, name", sql);
    }

    [Fact]
    public void ParameterizedQueriesPreventInjection()
    {
        var qb = new QueryBuilder("users");
        var maliciousInput = "'; DROP TABLE users; --";
        var (sql, parameters) = qb.Where("name", maliciousInput).Build();

        Assert.DoesNotContain("DROP", sql);
        Assert.Single(parameters);
        Assert.Equal(maliciousInput, parameters[0]);
    }

    [Fact]
    public void ComplexQuery()
    {
        var qb = new QueryBuilder("users", new List<string> { "id", "name", "email", "status" });
        var (sql, parameters) = qb
            .Select("id", "name", "email")
            .Where("status", "active")
            .Where("email", "test@example.com")
            .OrderBy("name", "ASC")
            .Build();

        Assert.Contains("SELECT id, name, email FROM users", sql);
        Assert.Contains("WHERE", sql);
        Assert.Contains("AND", sql);
        Assert.Contains("ORDER BY name ASC", sql);
        Assert.Equal(2, parameters.Count);
    }

    [Fact]
    public void EmptyTableNameThrows()
    {
        Assert.Throws<ArgumentException>(() => new QueryBuilder(""));
    }

    [Fact]
    public void InvalidDirectionDefaultsOrThrows()
    {
        var qb = new QueryBuilder("users", new List<string> { "id" });
        Assert.Throws<ArgumentException>(() => qb.OrderBy("id", "INVALID"));
    }
}
