import re


class QueryBuilder:
    """Builds SQL SELECT queries."""

    def __init__(self, table, allowed_columns=None):
        self.table = table
        self.allowed_columns = allowed_columns
        self._columns = ["*"]
        self._where_clause = None
        self._where_params = []
        self._order_by = None

    def select(self, *columns):
        """Set columns to select."""
        self._columns = list(columns) if columns else ["*"]
        return self

    def where(self, condition, value=None):
        """Add a WHERE condition. BUG: overwrites previous conditions."""
        if value is not None:
            # BUG 1: String interpolation instead of parameterized query
            self._where_clause = f"{condition} = '{value}'"
            self._where_params = []
        else:
            self._where_clause = condition
        return self

    def order_by(self, column, direction="ASC"):
        """Set ORDER BY clause. BUG: no column validation."""
        # BUG 2: No validation of column name - allows injection
        self._order_by = f"{column} {direction}"
        return self

    def build(self):
        """Build and return the SQL query string and params."""
        # BUG 3: No table name validation
        cols = ", ".join(self._columns)
        sql = f"SELECT {cols} FROM {self.table}"

        params = []
        if self._where_clause:
            sql += f" WHERE {self._where_clause}"
            params = self._where_params

        if self._order_by:
            sql += f" ORDER BY {self._order_by}"

        return sql, params
