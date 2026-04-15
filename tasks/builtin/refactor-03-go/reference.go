package solution

import (
	"fmt"
	"strconv"
	"strings"
)

type DataParser struct{}

func (p *DataParser) Parse(rawInput string) [][]string {
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

type DataValidator struct {
	ExpectedColumns int
	NumericColumns  map[int]bool
}

func NewDataValidator(expectedColumns int, numericColumns map[int]bool) *DataValidator {
	return &DataValidator{
		ExpectedColumns: expectedColumns,
		NumericColumns:  numericColumns,
	}
}

func (v *DataValidator) Validate(rows [][]string) ([][]interface{}, []string) {
	validRows := [][]interface{}{}
	errors := []string{}

	for i, row := range rows {
		if len(row) != v.ExpectedColumns {
			errors = append(errors, fmt.Sprintf("Row %d: expected %d columns, got %d", i, v.ExpectedColumns, len(row)))
			continue
		}

		parsedRow, parseError := v.parseRow(row, i)
		if parseError != "" {
			errors = append(errors, parseError)
		} else {
			validRows = append(validRows, parsedRow)
		}
	}

	return validRows, errors
}

func (v *DataValidator) parseRow(row []string, rowIdx int) ([]interface{}, string) {
	parsedRow := []interface{}{}
	for j, cell := range row {
		if v.NumericColumns[j] {
			val, err := strconv.ParseFloat(strings.TrimSpace(cell), 64)
			if err != nil {
				return nil, fmt.Sprintf("Row %d, column %d: '%s' is not a valid number", rowIdx, j, cell)
			}
			parsedRow = append(parsedRow, val)
		} else {
			parsedRow = append(parsedRow, strings.TrimSpace(cell))
		}
	}
	return parsedRow, ""
}

type DataTransformer struct {
	TextColumns     map[int]bool
	SourceColIdx    int
	Multiplier      float64
}

func NewDataTransformer(textColumns map[int]bool, sourceColIdx int, multiplier float64) *DataTransformer {
	return &DataTransformer{
		TextColumns:  textColumns,
		SourceColIdx: sourceColIdx,
		Multiplier:   multiplier,
	}
}

func (t *DataTransformer) Transform(rows [][]interface{}) [][]interface{} {
	normalized := t.normalizeTextColumns(rows)
	return t.computeDerivedColumn(normalized)
}

func (t *DataTransformer) normalizeTextColumns(rows [][]interface{}) [][]interface{} {
	normalizedRows := [][]interface{}{}
	for _, row := range rows {
		normalizedRow := []interface{}{}
		for j, cell := range row {
			if t.TextColumns[j] {
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

func (t *DataTransformer) computeDerivedColumn(rows [][]interface{}) [][]interface{} {
	resultRows := [][]interface{}{}
	for _, row := range rows {
		newRow := make([]interface{}, len(row)+1)
		copy(newRow, row)
		if val, ok := row[t.SourceColIdx].(float64); ok {
			newRow[len(row)] = val * t.Multiplier
		}
		resultRows = append(resultRows, newRow)
	}
	return resultRows
}

type DataFormatter struct {
	ColumnWidths []int
}

func NewDataFormatter(columnWidths []int) *DataFormatter {
	return &DataFormatter{ColumnWidths: columnWidths}
}

func (f *DataFormatter) Format(rows [][]interface{}) string {
	lines := []string{}
	for _, row := range rows {
		formattedCells := []string{}
		for i, cell := range row {
			width := f.ColumnWidths[i]
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
	parser := &DataParser{}
	rows := parser.Parse(rawInput)
	if len(rows) == 0 {
		return "ERROR: No data"
	}

	validator := NewDataValidator(3, map[int]bool{2: true})
	validRows, validationErrors := validator.Validate(rows)
	if len(validationErrors) > 0 {
		return "ERROR: " + strings.Join(validationErrors, "; ")
	}

	transformer := NewDataTransformer(map[int]bool{0: true, 1: true}, 2, 1.5)
	transformedRows := transformer.Transform(validRows)

	formatter := NewDataFormatter([]int{15, 12, 10, 10})
	return formatter.Format(transformedRows)
}
