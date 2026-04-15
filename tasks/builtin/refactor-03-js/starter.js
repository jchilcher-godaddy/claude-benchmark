function parseLines(rawInput) {
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

function validateRows(rows, expectedColumns) {
    const validRows = [];
    const errors = [];
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        if (row.length !== expectedColumns) {
            errors.push(`Row ${i}: expected ${expectedColumns} columns, got ${row.length}`);
        } else {
            validRows.push(row);
        }
    }
    return { validRows, errors };
}

function parseNumericColumns(rows, columnIndices) {
    const parsedRows = [];
    const errors = [];
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const parsedRow = [];
        let hasError = false;
        for (let j = 0; j < row.length; j++) {
            const cell = row[j];
            if (columnIndices.has(j)) {
                const num = parseFloat(cell.trim());
                if (isNaN(num)) {
                    errors.push(`Row ${i}, column ${j}: '${cell}' is not a valid number`);
                    hasError = true;
                    break;
                }
                parsedRow.push(num);
            } else {
                parsedRow.push(cell.trim());
            }
        }
        if (!hasError) {
            parsedRows.push(parsedRow);
        }
    }
    return { parsedRows, errors };
}

function normalizeTextColumns(rows, columnIndices) {
    const normalizedRows = [];
    for (const row of rows) {
        const normalizedRow = [];
        for (let j = 0; j < row.length; j++) {
            const cell = row[j];
            if (columnIndices.has(j) && typeof cell === 'string') {
                normalizedRow.push(cell.toUpperCase());
            } else {
                normalizedRow.push(cell);
            }
        }
        normalizedRows.push(normalizedRow);
    }
    return normalizedRows;
}

function computeDerivedColumn(rows, sourceColIdx, multiplier) {
    const resultRows = [];
    for (const row of rows) {
        const newRow = [...row, row[sourceColIdx] * multiplier];
        resultRows.push(newRow);
    }
    return resultRows;
}

function formatRowsAsTable(rows, columnWidths) {
    const lines = [];
    for (const row of rows) {
        const formattedCells = [];
        for (let i = 0; i < row.length; i++) {
            const cell = row[i];
            const width = columnWidths[i];
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

function processData(rawInput) {
    const rows = parseLines(rawInput);
    if (rows.length === 0) {
        return 'ERROR: No data';
    }

    const { validRows, errors: validationErrors } = validateRows(rows, 3);
    if (validationErrors.length > 0) {
        return 'ERROR: ' + validationErrors.join('; ');
    }

    const { parsedRows, errors: parseErrors } = parseNumericColumns(validRows, new Set([2]));
    if (parseErrors.length > 0) {
        return 'ERROR: ' + parseErrors.join('; ');
    }

    const normalizedRows = normalizeTextColumns(parsedRows, new Set([0, 1]));
    const computedRows = computeDerivedColumn(normalizedRows, 2, 1.5);
    const result = formatRowsAsTable(computedRows, [15, 12, 10, 10]);

    return result;
}

module.exports = { processData };
