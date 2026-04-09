import re


class QueryBuilder:
    """Builds safe parameterized SQL SELECT queries."""

    VALID_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    def __init__(self, table, allowed_columns=None):
        self.allowed_columns = allowed_columns
        self._validate_name(table, "table")
        self.table = table
        self._columns = ["*"]
        self._where_conditions = []
        self._where_params = []
        self._order_by = None

    def _validate_name(self, name, kind="column"):
        if not self.VALID_NAME_PATTERN.match(name):
            raise ValueError(f"Invalid {kind} name: {name!r}")
        if self.allowed_columns and kind == "column" and name != "*":
            if name not in self.allowed_columns:
                raise ValueError(
                    f"Column {name!r} not in allowed columns: {self.allowed_columns}"
                )

    def select(self, *columns):
        """Set columns to select."""
        for col in columns:
            self._validate_name(col, "column")
        self._columns = list(columns) if columns else ["*"]
        return self

    def where(self, condition, value=None):
        """Add a WHERE condition with parameterized value. Chains with AND."""
        if value is not None:
            self._validate_name(condition, "column")
            self._where_conditions.append(f"{condition} = ?")
            self._where_params.append(value)
        else:
            self._where_conditions.append(condition)
        return self

    def order_by(self, column, direction="ASC"):
        """Set ORDER BY clause with validation."""
        self._validate_name(column, "column")
        direction = direction.upper()
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"Invalid direction: {direction!r}")
        self._order_by = (column, direction)
        return self

    def build(self):
        """Build and return the SQL query string and params."""
        cols = ", ".join(self._columns)
        sql = f"SELECT {cols} FROM {self.table}"

        params = list(self._where_params)
        if self._where_conditions:
            sql += " WHERE " + " AND ".join(self._where_conditions)

        if self._order_by:
            col, direction = self._order_by
            sql += f" ORDER BY {col} {direction}"

        return sql, params
