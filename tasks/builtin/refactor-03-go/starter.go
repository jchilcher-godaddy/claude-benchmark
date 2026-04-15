package solution

import (
	"fmt"
	"strconv"
	"strings"
)

func parseLines(rawInput string) [][]string {
	lines := strings.Split(strings.TrimSpace(rawInput), "\n")
	rows := [][]string{}
	for _, line := range lines {
		if strings.TrimSpace(line) != "" {
			parts := strings.Split(line, ",")
			rows = append(rows, parts)
		}
	}
	return rows
}

func validateRows(rows [][]string, expectedColumns int) ([][]string, []string) {
	validRows := [][]string{}
	errors := []string{}
	for i, row := range rows {
		if len(row) != expectedColumns {
			errors = append(errors, fmt.Sprintf("Row %d: expected %d columns, got %d", i, expectedColumns, len(row)))
		} else {
			validRows = append(validRows, row)
		}
	}
	return validRows, errors
}

func parseNumericColumns(rows [][]string, columnIndices map[int]bool) ([][]interface{}, []string) {
	parsedRows := [][]interface{}{}
	errors := []string{}
	for i, row := range rows {
		parsedRow := []interface{}{}
		hasError := false
		for j, cell := range row {
			if columnIndices[j] {
				val, err := strconv.ParseFloat(strings.TrimSpace(cell), 64)
				if err != nil {
					errors = append(errors, fmt.Sprintf("Row %d, column %d: '%s' is not a valid number", i, j, cell))
					hasError = true
					break
				}
				parsedRow = append(parsedRow, val)
			} else {
				parsedRow = append(parsedRow, strings.TrimSpace(cell))
			}
		}
		if !hasError {
			parsedRows = append(parsedRows, parsedRow)
		}
	}
	return parsedRows, errors
}

func normalizeTextColumns(rows [][]interface{}, columnIndices map[int]bool) [][]interface{} {
	normalizedRows := [][]interface{}{}
	for _, row := range rows {
		normalizedRow := []interface{}{}
		for j, cell := range row {
			if columnIndices[j] {
				if str, ok := cell.(string); ok {
					normalizedRow = append(normalizedRow, strings.ToUpper(str))
				} else {
					normalizedRow = append(normalizedRow, cell)
				}
			} else {
				normalizedRow = append(normalizedRow, cell)
			}
		}
		normalizedRows = append(normalizedRows, normalizedRow)
	}
	return normalizedRows
}

func computeDerivedColumn(rows [][]interface{}, sourceColIdx int, multiplier float64) [][]interface{} {
	resultRows := [][]interface{}{}
	for _, row := range rows {
		newRow := make([]interface{}, len(row)+1)
		copy(newRow, row)
		if val, ok := row[sourceColIdx].(float64); ok {
			newRow[len(row)] = val * multiplier
		}
		resultRows = append(resultRows, newRow)
	}
	return resultRows
}

func formatRowsAsTable(rows [][]interface{}, columnWidths []int) string {
	lines := []string{}
	for _, row := range rows {
		formattedCells := []string{}
		for i, cell := range row {
			width := columnWidths[i]
			if val, ok := cell.(float64); ok {
				formattedCells = append(formattedCells, fmt.Sprintf("%*.2f", width, val))
			} else {
				formattedCells = append(formattedCells, fmt.Sprintf("%-*s", width, fmt.Sprint(cell)))
			}
		}
		lines = append(lines, strings.Join(formattedCells, " | "))
	}
	return strings.Join(lines, "\n")
}

func ProcessData(rawInput string) string {
	rows := parseLines(rawInput)
	if len(rows) == 0 {
		return "ERROR: No data"
	}

	validRows, validationErrors := validateRows(rows, 3)
	if len(validationErrors) > 0 {
		return "ERROR: " + strings.Join(validationErrors, "; ")
	}

	parsedRows, parseErrors := parseNumericColumns(validRows, map[int]bool{2: true})
	if len(parseErrors) > 0 {
		return "ERROR: " + strings.Join(parseErrors, "; ")
	}

	normalizedRows := normalizeTextColumns(parsedRows, map[int]bool{0: true, 1: true})
	computedRows := computeDerivedColumn(normalizedRows, 2, 1.5)
	result := formatRowsAsTable(computedRows, []int{15, 12, 10, 10})

	return result
}
