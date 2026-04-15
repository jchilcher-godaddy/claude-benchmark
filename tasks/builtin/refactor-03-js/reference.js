class DataParser {
    parse(rawInput) {
        const lines = rawInput.trim().split('\n');
        const rows = [];
        for (const line of lines) {
            if (line.trim()) {
                const parts = line.split(',');
                rows.push(parts);
            }
        }
        return rows;
    }
}

class DataValidator {
    constructor(expectedColumns, numericColumns) {
        this.expectedColumns = expectedColumns;
        this.numericColumns = numericColumns;
    }

    validate(rows) {
        const validRows = [];
        const errors = [];

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            if (row.length !== this.expectedColumns) {
                errors.push(`Row ${i}: expected ${this.expectedColumns} columns, got ${row.length}`);
                continue;
            }

            const { parsedRow, error } = this._parseRow(row, i);
            if (error) {
                errors.push(error);
            } else {
                validRows.push(parsedRow);
            }
        }

        return { validRows, errors };
    }

    _parseRow(row, rowIdx) {
        const parsedRow = [];
        for (let j = 0; j < row.length; j++) {
            const cell = row[j];
            if (this.numericColumns.has(j)) {
                const num = parseFloat(cell.trim());
                if (isNaN(num)) {
                    return { parsedRow: [], error: `Row ${rowIdx}, column ${j}: '${cell}' is not a valid number` };
                }
                parsedRow.push(num);
            } else {
                parsedRow.push(cell.trim());
            }
        }
        return { parsedRow, error: null };
    }
}

class DataTransformer {
    constructor(textColumns) {
        this.textColumns = textColumns;
    }

    transform(rows, sourceColIdx, multiplier) {
        const normalizedRows = this._normalizeText(rows);
        const computedRows = this._addComputedColumn(normalizedRows, sourceColIdx, multiplier);
        return computedRows;
    }

    _normalizeText(rows) {
        const normalizedRows = [];
        for (const row of rows) {
            const normalizedRow = [];
            for (let j = 0; j < row.length; j++) {
                const cell = row[j];
                if (this.textColumns.has(j) && typeof cell === 'string') {
                    normalizedRow.push(cell.toUpperCase());
                } else {
                    normalizedRow.push(cell);
                }
            }
            normalizedRows.push(normalizedRow);
        }
        return normalizedRows;
    }

    _addComputedColumn(rows, sourceColIdx, multiplier) {
        const resultRows = [];
        for (const row of rows) {
            const newRow = [...row, row[sourceColIdx] * multiplier];
            resultRows.push(newRow);
        }
        return resultRows;
    }
}

class DataFormatter {
    constructor(columnWidths) {
        this.columnWidths = columnWidths;
    }

    format(rows) {
        const lines = [];
        for (const row of rows) {
            const formattedCells = [];
            for (let i = 0; i < row.length; i++) {
                const cell = row[i];
                const width = this.columnWidths[i];
                if (typeof cell === 'number') {
                    formattedCells.push(cell.toFixed(2).padStart(width));
                } else {
                    formattedCells.push(String(cell).padEnd(width));
                }
            }
            lines.push(formattedCells.join(' | '));
        }
        return lines.join('\n');
    }
}

function processData(rawInput) {
    const parser = new DataParser();
    const rows = parser.parse(rawInput);

    if (rows.length === 0) {
        return 'ERROR: No data';
    }

    const validator = new DataValidator(3, new Set([2]));
    const { validRows, errors } = validator.validate(rows);

    if (errors.length > 0) {
        return 'ERROR: ' + errors.join('; ');
    }

    const transformer = new DataTransformer(new Set([0, 1]));
    const transformedRows = transformer.transform(validRows, 2, 1.5);

    const formatter = new DataFormatter([15, 12, 10, 10]);
    const result = formatter.format(transformedRows);

    return result;
}

module.exports = { processData };
