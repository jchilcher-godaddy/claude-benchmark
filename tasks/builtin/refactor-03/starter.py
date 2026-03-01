"""Procedural CSV-like data processor."""


def parse_lines(raw_input):
    lines = raw_input.strip().split("\n")
    rows = []
    for line in lines:
        if line.strip():
            parts = line.split(",")
            rows.append(parts)
    return rows


def validate_rows(rows, expected_columns):
    valid_rows = []
    errors = []
    for i, row in enumerate(rows):
        if len(row) != expected_columns:
            errors.append(f"Row {i}: expected {expected_columns} columns, got {len(row)}")
        else:
            valid_rows.append(row)
    return valid_rows, errors


def parse_numeric_columns(rows, column_indices):
    parsed_rows = []
    errors = []
    for i, row in enumerate(rows):
        parsed_row = []
        has_error = False
        for j, cell in enumerate(row):
            if j in column_indices:
                try:
                    parsed_row.append(float(cell.strip()))
                except ValueError:
                    errors.append(f"Row {i}, column {j}: '{cell}' is not a valid number")
                    has_error = True
                    break
            else:
                parsed_row.append(cell.strip())
        if not has_error:
            parsed_rows.append(parsed_row)
    return parsed_rows, errors


def normalize_text_columns(rows, column_indices):
    normalized_rows = []
    for row in rows:
        normalized_row = []
        for j, cell in enumerate(row):
            if j in column_indices and isinstance(cell, str):
                normalized_row.append(cell.upper())
            else:
                normalized_row.append(cell)
        normalized_rows.append(normalized_row)
    return normalized_rows


def compute_derived_column(rows, source_col_idx, multiplier):
    result_rows = []
    for row in rows:
        new_row = row + [row[source_col_idx] * multiplier]
        result_rows.append(new_row)
    return result_rows


def format_rows_as_table(rows, column_widths):
    lines = []
    for row in rows:
        formatted_cells = []
        for i, cell in enumerate(row):
            width = column_widths[i]
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
    rows = parse_lines(raw_input)
    if not rows:
        return "ERROR: No data"

    valid_rows, validation_errors = validate_rows(rows, 3)
    if validation_errors:
        return "ERROR: " + "; ".join(validation_errors)

    parsed_rows, parse_errors = parse_numeric_columns(valid_rows, {2})
    if parse_errors:
        return "ERROR: " + "; ".join(parse_errors)

    normalized_rows = normalize_text_columns(parsed_rows, {0, 1})
    computed_rows = compute_derived_column(normalized_rows, 2, 1.5)
    result = format_rows_as_table(computed_rows, [15, 12, 10, 10])

    return result
