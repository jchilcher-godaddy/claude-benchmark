"""Tests for bug-fix-04: SQL query builder with injection vulnerabilities."""

import pytest

from solution import QueryBuilder


class TestBasicQueryBuilding:
    def test_simple_select_all(self):
        qb = QueryBuilder("users")
        sql, params = qb.build()
        assert sql == "SELECT * FROM users"
        assert params == []

    def test_select_specific_columns(self):
        qb = QueryBuilder("users", allowed_columns=["name", "email"])
        sql, params = qb.select("name", "email").build()
        assert "name" in sql
        assert "email" in sql
        assert params == []

    def test_where_with_value(self):
        qb = QueryBuilder("users", allowed_columns=["name", "age"])
        sql, params = qb.where("name", "Alice").build()
        assert "?" in sql or "%s" in sql
        assert "Alice" in params

    def test_order_by(self):
        qb = QueryBuilder("users", allowed_columns=["name"])
        sql, params = qb.select("name").order_by("name").build()
        assert "ORDER BY name" in sql


class TestParameterizedQueries:
    def test_where_value_not_interpolated(self):
        """Values must be in params list, not interpolated into SQL string."""
        qb = QueryBuilder("users", allowed_columns=["name"])
        sql, params = qb.where("name", "Alice").build()
        assert "Alice" not in sql
        assert "Alice" in params

    def test_where_uses_placeholder(self):
        qb = QueryBuilder("users", allowed_columns=["name"])
        sql, params = qb.where("name", "test").build()
        assert "?" in sql or "%s" in sql

    def test_multiple_where_params(self):
        qb = QueryBuilder("users", allowed_columns=["name", "age"])
        sql, params = qb.where("name", "Alice").where("age", 30).build()
        assert len(params) == 2
        assert "Alice" in params
        assert 30 in params


class TestSQLInjectionPrevention:
    def test_injection_in_where_value(self):
        """SQL injection via value should be prevented by parameterization."""
        qb = QueryBuilder("users", allowed_columns=["name"])
        sql, params = qb.where("name", "'; DROP TABLE users; --").build()
        assert "DROP TABLE" not in sql
        assert "'; DROP TABLE users; --" in params

    def test_injection_in_order_by(self):
        """Injection via order_by column name should be rejected."""
        qb = QueryBuilder("users")
        with pytest.raises(ValueError):
            qb.order_by("name; DROP TABLE users")

    def test_injection_in_table_name(self):
        """Injection via table name should be rejected."""
        with pytest.raises(ValueError):
            QueryBuilder("users; DROP TABLE users")

    def test_injection_in_column_name(self):
        """Injection via column name should be rejected."""
        qb = QueryBuilder("users", allowed_columns=["name"])
        with pytest.raises(ValueError):
            qb.select("name; DROP TABLE users")


class TestColumnValidation:
    def test_rejects_column_not_in_whitelist(self):
        qb = QueryBuilder("users", allowed_columns=["name", "email"])
        with pytest.raises(ValueError):
            qb.select("password")

    def test_allows_column_in_whitelist(self):
        qb = QueryBuilder("users", allowed_columns=["name", "email"])
        sql, _ = qb.select("name").build()
        assert "name" in sql

    def test_order_by_validates_column(self):
        qb = QueryBuilder("users", allowed_columns=["name"])
        with pytest.raises(ValueError):
            qb.order_by("nonexistent")


class TestWhereChaining:
    def test_multiple_where_chains_with_and(self):
        qb = QueryBuilder("users", allowed_columns=["name", "age"])
        sql, params = qb.where("name", "Alice").where("age", 30).build()
        assert "AND" in sql
        assert len(params) == 2

    def test_three_where_conditions(self):
        qb = QueryBuilder("users", allowed_columns=["name", "age", "city"])
        sql, params = (
            qb.where("name", "Alice").where("age", 30).where("city", "NYC").build()
        )
        assert sql.count("AND") == 2
        assert len(params) == 3
