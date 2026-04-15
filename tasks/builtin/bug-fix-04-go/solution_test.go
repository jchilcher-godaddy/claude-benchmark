package solution

import (
	"reflect"
	"strings"
	"testing"
)

func TestBasicQuery(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name", "email"})
	sql, params, err := qb.Build()
	if err != nil {
		t.Fatalf("Build error: %v", err)
	}
	if sql != "SELECT * FROM users" {
		t.Errorf("sql = %q, want %q", sql, "SELECT * FROM users")
	}
	if len(params) != 0 {
		t.Errorf("params length = %d, want 0", len(params))
	}
}

func TestSelectColumns(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name", "email"})
	qb.Select("id", "name")
	sql, _, err := qb.Build()
	if err != nil {
		t.Fatalf("Build error: %v", err)
	}
	if !strings.Contains(sql, "id") || !strings.Contains(sql, "name") {
		t.Errorf("sql = %q, want to contain 'id' and 'name'", sql)
	}
}

func TestWhereParameterized(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name", "email"})
	qb.Where("name", "Alice")
	sql, params, err := qb.Build()
	if err != nil {
		t.Fatalf("Build error: %v", err)
	}
	if !strings.Contains(sql, "?") {
		t.Errorf("sql = %q, want to contain '?'", sql)
	}
	if len(params) != 1 || params[0] != "Alice" {
		t.Errorf("params = %v, want [Alice]", params)
	}
	if strings.Contains(sql, "Alice") {
		t.Errorf("sql contains literal value 'Alice', should use parameter")
	}
}

func TestMultipleWhereChaining(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name", "email", "age"})
	qb.Where("name", "Alice")
	qb.Where("age", 30)
	sql, params, err := qb.Build()
	if err != nil {
		t.Fatalf("Build error: %v", err)
	}
	if !strings.Contains(sql, "AND") {
		t.Errorf("sql = %q, want to contain 'AND'", sql)
	}
	if len(params) != 2 {
		t.Errorf("params length = %d, want 2", len(params))
	}
}

func TestOrderBy(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name", "email"})
	qb.OrderBy("name", "ASC")
	sql, _, err := qb.Build()
	if err != nil {
		t.Fatalf("Build error: %v", err)
	}
	if !strings.Contains(sql, "ORDER BY") || !strings.Contains(sql, "name") {
		t.Errorf("sql = %q, want to contain 'ORDER BY name'", sql)
	}
}

func TestInvalidTableName(t *testing.T) {
	_, err := NewQueryBuilder("users; DROP TABLE users;", []string{"id"})
	if err == nil {
		t.Error("expected error for invalid table name")
	}
}

func TestInvalidColumnName(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name"})
	_, err := qb.Select("id; DROP TABLE users;")
	if err == nil {
		t.Error("expected error for invalid column name")
	}
}

func TestColumnNotInWhitelist(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name"})
	_, err := qb.Select("password")
	if err == nil {
		t.Error("expected error for column not in whitelist")
	}
}

func TestOrderByValidation(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name"})
	_, err := qb.OrderBy("name; DROP TABLE users;", "ASC")
	if err == nil {
		t.Error("expected error for invalid order by column")
	}
}

func TestWhereColumnValidation(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name"})
	_, err := qb.Where("email", "test@example.com")
	if err == nil {
		t.Error("expected error for where column not in whitelist")
	}
}

func TestComplexQuery(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name", "email", "age"})
	qb.Select("id", "name", "email")
	qb.Where("age", 25)
	qb.Where("name", "Alice")
	qb.OrderBy("name", "DESC")
	sql, params, err := qb.Build()
	if err != nil {
		t.Fatalf("Build error: %v", err)
	}
	if !strings.Contains(sql, "SELECT") || !strings.Contains(sql, "WHERE") || !strings.Contains(sql, "ORDER BY") {
		t.Errorf("sql = %q, want complete query", sql)
	}
	if len(params) != 2 {
		t.Errorf("params length = %d, want 2", len(params))
	}
}

func TestNoSQLInjectionInWhere(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name"})
	qb.Where("name", "'; DROP TABLE users; --")
	sql, params, _ := qb.Build()
	if strings.Contains(sql, "DROP TABLE") {
		t.Errorf("sql contains injected DROP TABLE")
	}
	if len(params) != 1 || params[0] != "'; DROP TABLE users; --" {
		t.Error("malicious input should be passed as parameter, not interpolated")
	}
}

func TestInvalidDirection(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name"})
	_, err := qb.OrderBy("name", "INVALID")
	if err == nil {
		t.Error("expected error for invalid direction")
	}
}

func TestEmptyWhitelist(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{})
	_, err := qb.Select("id")
	if err == nil {
		t.Error("expected error when selecting column not in empty whitelist")
	}
}

func TestNilWhitelist(t *testing.T) {
	qb, _ := NewQueryBuilder("users", nil)
	_, err := qb.Select("id", "name")
	if err != nil {
		t.Errorf("should allow any valid identifier when whitelist is nil: %v", err)
	}
}

func TestParameterOrder(t *testing.T) {
	qb, _ := NewQueryBuilder("users", []string{"id", "name", "age"})
	qb.Where("name", "Alice")
	qb.Where("age", 30)
	_, params, _ := qb.Build()
	expected := []interface{}{"Alice", 30}
	if !reflect.DeepEqual(params, expected) {
		t.Errorf("params = %v, want %v", params, expected)
	}
}
