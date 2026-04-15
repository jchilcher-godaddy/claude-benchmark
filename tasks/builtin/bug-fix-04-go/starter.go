package solution

import (
	"fmt"
)

type QueryBuilder struct {
	table          string
	allowedColumns []string
	columns        []string
	whereClause    string
	whereParams    []interface{}
	orderBy        string
}

func NewQueryBuilder(table string, allowedColumns []string) *QueryBuilder {
	return &QueryBuilder{
		table:          table,
		allowedColumns: allowedColumns,
		columns:        []string{"*"},
		whereParams:    []interface{}{},
	}
}

func (qb *QueryBuilder) Select(columns ...string) *QueryBuilder {
	if len(columns) > 0 {
		qb.columns = columns
	} else {
		qb.columns = []string{"*"}
	}
	return qb
}

func (qb *QueryBuilder) Where(condition string, value interface{}) *QueryBuilder {
	if value != nil {
		qb.whereClause = fmt.Sprintf("%s = '%v'", condition, value)
		qb.whereParams = []interface{}{}
	} else {
		qb.whereClause = condition
	}
	return qb
}

func (qb *QueryBuilder) OrderBy(column string, direction string) *QueryBuilder {
	if direction == "" {
		direction = "ASC"
	}
	qb.orderBy = fmt.Sprintf("%s %s", column, direction)
	return qb
}

func (qb *QueryBuilder) Build() (string, []interface{}, error) {
	cols := ""
	for i, col := range qb.columns {
		if i > 0 {
			cols += ", "
		}
		cols += col
	}

	sql := fmt.Sprintf("SELECT %s FROM %s", cols, qb.table)

	params := []interface{}{}
	if qb.whereClause != "" {
		sql += fmt.Sprintf(" WHERE %s", qb.whereClause)
		params = qb.whereParams
	}

	if qb.orderBy != "" {
		sql += fmt.Sprintf(" ORDER BY %s", qb.orderBy)
	}

	return sql, params, nil
}
