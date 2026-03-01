"""Class-based CSV-like data processor with separation of concerns."""


class DataParser:
    """Parse raw CSV-like input into structured rows."""

    def parse(self, raw_input: str) -> list[list[str]]:
        """Parse raw input into rows of strings.

        Args:
            raw_input: CSV-like string input

        Returns:
            List of rows, where each row is a list of cell values
        """
        lines = raw_input.strip().split("\n")
        rows = []
        for line in lines:
            if line.strip():
                parts = line.split(",")
                rows.append(parts)
        return rows


class DataValidator:
    """Validate parsed data against schema requirements."""

    def __init__(self, expected_columns: int, numeric_columns: set[int]):
        """Initialize validator.

        Args:
            expected_columns: Expected number of columns per row
            numeric_columns: Set of column indices that must be numeric
        """
        self.expected_columns = expected_columns
        self.numeric_columns = numeric_columns

    def validate(self, rows: list[list[str]]) -> tuple[list[list], list[str]]:
        """Validate and parse rows.

        Args:
            rows: Parsed rows to validate

        Returns:
            Tuple of (valid_rows, error_messages)
        """
        valid_rows = []
        errors = []

        for i, row in enumerate(rows):
            if len(row) != self.expected_columns:
                errors.append(
                    f"Row {i}: expected {self.expected_columns} columns, got {len(row)}"
                )
                continue

            parsed_row, parse_error = self._parse_row(row, i)
            if parse_error:
                errors.append(parse_error)
            else:
                valid_rows.append(parsed_row)

        return valid_rows, errors

    def _parse_row(self, row: list[str], row_idx: int) -> tuple[list, str | None]:
        """Parse a single row, converting numeric columns.

        Args:
            row: Row to parse
            row_idx: Row index for error messages

        Returns:
            Tuple of (parsed_row, error_message)
        """
        parsed_row = []
        for j, cell in enumerate(row):
            if j in self.numeric_columns:
                try:
                    parsed_row.append(float(cell.strip()))
                except ValueError:
                    return [], f"Row {row_idx}, column {j}: '{cell}' is not a valid number"
            else:
                parsed_row.append(cell.strip())
        return parsed_row, None


class DataTransformer:
    """Transform data by normalizing and computing derived values."""

    def __init__(self, text_columns: set[int]):
        """Initialize transformer.

        Args:
            text_columns: Set of column indices to normalize to uppercase
        """
        self.text_columns = text_columns

    def transform(
        self, rows: list[list], source_col_idx: int, multiplier: float
    ) -> list[list]:
        """Transform data by normalizing text and adding computed column.

        Args:
            rows: Rows to transform
            source_col_idx: Source column index for computed value
            multiplier: Multiplier for computed column

        Returns:
            Transformed rows with additional computed column
        """
        normalized_rows = self._normalize_text(rows)
        computed_rows = self._add_computed_column(
            normalized_rows, source_col_idx, multiplier
        )
        return computed_rows

    def _normalize_text(self, rows: list[list]) -> list[list]:
        """Normalize text columns to uppercase.

        Args:
            rows: Rows to normalize

        Returns:
            Rows with normalized text columns
        """
        normalized_rows = []
        for row in rows:
            normalized_row = []
            for j, cell in enumerate(row):
                if j in self.text_columns and isinstance(cell, str):
                    normalized_row.append(cell.upper())
                else:
                    normalized_row.append(cell)
            normalized_rows.append(normalized_row)
        return normalized_rows

    def _add_computed_column(
        self, rows: list[list], source_col_idx: int, multiplier: float
    ) -> list[list]:
        """Add computed column based on source column.

        Args:
            rows: Rows to process
            source_col_idx: Source column index
            multiplier: Multiplier to apply

        Returns:
            Rows with additional computed column
        """
        result_rows = []
        for row in rows:
            new_row = row + [row[source_col_idx] * multiplier]
            result_rows.append(new_row)
        return result_rows


class DataFormatter:
    """Format data as a text table."""

    def __init__(self, column_widths: list[int]):
        """Initialize formatter.

        Args:
            column_widths: Width for each column
        """
        self.column_widths = column_widths

    def format(self, rows: list[list]) -> str:
        """Format rows as a text table.

        Args:
            rows: Rows to format

        Returns:
            Formatted table string
        """
        lines = []
        for row in rows:
            formatted_cells = []
            for i, cell in enumerate(row):
                width = self.column_widths[i]
                if isinstance(cell, float):
                    formatted_cells.append(f"{cell:>{width}.2f}")
                else:
                    formatted_cells.append(f"{str(cell):<{width}}")
            lines.append(" | ".join(formatted_cells))
        return "\n".join(lines)


def process_data(raw_input: str) -> str:
    """Process CSV-like data: parse, validate, transform, format.

    Args:
        raw_input: CSV-like input with 3 columns: name,category,value

    Returns:
        Formatted table string with 4 columns (adds computed column)
    """
    parser = DataParser()
    rows = parser.parse(raw_input)

    if not rows:
        return "ERROR: No data"

    validator = DataValidator(expected_columns=3, numeric_columns={2})
    valid_rows, errors = validator.validate(rows)

    if errors:
        return "ERROR: " + "; ".join(errors)

    transformer = DataTransformer(text_columns={0, 1})
    transformed_rows = transformer.transform(valid_rows, source_col_idx=2, multiplier=1.5)

    formatter = DataFormatter(column_widths=[15, 12, 10, 10])
    result = formatter.format(transformed_rows)

    return result
