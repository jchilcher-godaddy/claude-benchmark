package solution

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
)

type QueryBuilder struct {
	table            string
	allowedColumns   []string
	columns          []string
	whereConditions  []string
	whereParams      []interface{}
	orderByColumn    string
	orderByDirection string
}

var validNamePattern = regexp.MustCompile(`^[a-zA-Z_][a-zA-Z0-9_]*$`)

func NewQueryBuilder(table string, allowedColumns []string) (*QueryBuilder, error) {
	if err := validateName(table, "table", nil); err != nil {
		return nil, err
	}
	return &QueryBuilder{
		table:           table,
		allowedColumns:  allowedColumns,
		columns:         []string{"*"},
		whereConditions: []string{},
		whereParams:     []interface{}{},
	}, nil
}

func validateName(name string, kind string, allowedColumns []string) error {
	if !validNamePattern.MatchString(name) {
		return fmt.Errorf("invalid %s name: %q", kind, name)
	}
	if allowedColumns != nil && kind == "column" && name != "*" {
		found := false
		for _, col := range allowedColumns {
			if col == name {
				found = true
				break
			}
		}
		if !found {
			return fmt.Errorf("column %q not in allowed columns", name)
		}
	}
	return nil
}

func (qb *QueryBuilder) Select(columns ...string) (*QueryBuilder, error) {
	for _, col := range columns {
		if err := validateName(col, "column", qb.allowedColumns); err != nil {
			return nil, err
		}
	}
	if len(columns) > 0 {
		qb.columns = columns
	} else {
		qb.columns = []string{"*"}
	}
	return qb, nil
}

func (qb *QueryBuilder) Where(condition string, value interface{}) (*QueryBuilder, error) {
	if value != nil {
		if err := validateName(condition, "column", qb.allowedColumns); err != nil {
			return nil, err
		}
		qb.whereConditions = append(qb.whereConditions, fmt.Sprintf("%s = ?", condition))
		qb.whereParams = append(qb.whereParams, value)
	} else {
		qb.whereConditions = append(qb.whereConditions, condition)
	}
	return qb, nil
}

func (qb *QueryBuilder) OrderBy(column string, direction string) (*QueryBuilder, error) {
	if err := validateName(column, "column", qb.allowedColumns); err != nil {
		return nil, err
	}
	direction = strings.ToUpper(direction)
	if direction != "ASC" && direction != "DESC" {
		return nil, fmt.Errorf("invalid direction: %q", direction)
	}
	qb.orderByColumn = column
	qb.orderByDirection = direction
	return qb, nil
}

func (qb *QueryBuilder) Build() (string, []interface{}, error) {
	if len(qb.columns) == 0 {
		return "", nil, errors.New("no columns selected")
	}

	cols := strings.Join(qb.columns, ", ")
	sql := fmt.Sprintf("SELECT %s FROM %s", cols, qb.table)

	params := make([]interface{}, len(qb.whereParams))
	copy(params, qb.whereParams)

	if len(qb.whereConditions) > 0 {
		sql += " WHERE " + strings.Join(qb.whereConditions, " AND ")
	}

	if qb.orderByColumn != "" {
		sql += fmt.Sprintf(" ORDER BY %s %s", qb.orderByColumn, qb.orderByDirection)
	}

	return sql, params, nil
}
