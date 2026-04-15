package solution

import (
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"testing"
)

func TestEmptyRecords(t *testing.T) {
	result := ProcessRecords([]Record{})
	if result.ActiveTotal != 0 || result.PendingTotal != 0 {
		t.Errorf("empty records should return zero totals")
	}
}

func TestSingleActiveRecord(t *testing.T) {
	records := []Record{
		{"status": "active", "amount": 100.0, "priority": "low"},
	}
	result := ProcessRecords(records)
	if result.ActiveTotal != 100.0 {
		t.Errorf("ActiveTotal = %f, want 100.0", result.ActiveTotal)
	}
	if result.ActiveHighPriorityCount != 0 {
		t.Errorf("ActiveHighPriorityCount = %d, want 0", result.ActiveHighPriorityCount)
	}
}

func TestHighPriorityAggregation(t *testing.T) {
	records := []Record{
		{"status": "active", "amount": 50.0, "priority": "high"},
		{"status": "pending", "amount": 75.0, "priority": "high"},
		{"status": "active", "amount": 25.0, "priority": "low"},
	}
	result := ProcessRecords(records)
	if result.HighPriorityTotal != 125.0 {
		t.Errorf("HighPriorityTotal = %f, want 125.0", result.HighPriorityTotal)
	}
}

func TestPendingRecords(t *testing.T) {
	records := []Record{
		{"status": "pending", "amount": 100.0, "priority": "low"},
		{"status": "pending", "amount": 50.0, "priority": "high"},
	}
	result := ProcessRecords(records)
	if result.PendingTotal != 150.0 {
		t.Errorf("PendingTotal = %f, want 150.0", result.PendingTotal)
	}
	if result.PendingHighPriorityCount != 1 {
		t.Errorf("PendingHighPriorityCount = %d, want 1", result.PendingHighPriorityCount)
	}
}

func TestActiveHighPriorityCounting(t *testing.T) {
	records := []Record{
		{"status": "active", "amount": 100.0, "priority": "high"},
		{"status": "active", "amount": 50.0, "priority": "high"},
		{"status": "active", "amount": 25.0, "priority": "low"},
		{"status": "pending", "amount": 75.0, "priority": "high"},
	}
	result := ProcessRecords(records)
	if result.ActiveHighPriorityCount != 2 {
		t.Errorf("ActiveHighPriorityCount = %d, want 2", result.ActiveHighPriorityCount)
	}
	if result.PendingHighPriorityCount != 1 {
		t.Errorf("PendingHighPriorityCount = %d, want 1", result.PendingHighPriorityCount)
	}
}

func TestNegativeAmountsIgnored(t *testing.T) {
	records := []Record{
		{"status": "active", "amount": -50.0, "priority": "high"},
		{"status": "active", "amount": 100.0, "priority": "high"},
	}
	result := ProcessRecords(records)
	if result.ActiveTotal != 100.0 {
		t.Errorf("ActiveTotal = %f, want 100.0 (negatives ignored)", result.ActiveTotal)
	}
}

func TestMissingFields(t *testing.T) {
	records := []Record{
		{"status": "active"},
		{"amount": 100.0},
		{"priority": "high"},
	}
	result := ProcessRecords(records)
	if result.ActiveTotal != 0 {
		t.Errorf("ActiveTotal = %f, want 0 (no amount)", result.ActiveTotal)
	}
}

func TestMixedRecords(t *testing.T) {
	records := []Record{
		{"status": "active", "amount": 100.0, "priority": "high"},
		{"status": "pending", "amount": 50.0, "priority": "high"},
		{"status": "active", "amount": 75.0, "priority": "low"},
		{"status": "inactive", "amount": 25.0, "priority": "high"},
	}
	result := ProcessRecords(records)
	if result.ActiveTotal != 175.0 {
		t.Errorf("ActiveTotal = %f, want 175.0", result.ActiveTotal)
	}
	if result.PendingTotal != 50.0 {
		t.Errorf("PendingTotal = %f, want 50.0", result.PendingTotal)
	}
	if result.HighPriorityTotal != 175.0 {
		t.Errorf("HighPriorityTotal = %f, want 175.0", result.HighPriorityTotal)
	}
	if result.ActiveHighPriorityCount != 1 {
		t.Errorf("ActiveHighPriorityCount = %d, want 1", result.ActiveHighPriorityCount)
	}
	if result.PendingHighPriorityCount != 1 {
		t.Errorf("PendingHighPriorityCount = %d, want 1", result.PendingHighPriorityCount)
	}
}

func TestZeroAmounts(t *testing.T) {
	records := []Record{
		{"status": "active", "amount": 0.0, "priority": "high"},
		{"status": "active", "amount": 100.0, "priority": "high"},
	}
	result := ProcessRecords(records)
	if result.ActiveTotal != 100.0 {
		t.Errorf("ActiveTotal = %f, want 100.0 (zero amounts ignored)", result.ActiveTotal)
	}
}

func TestHelperFunctionsExist(t *testing.T) {
	fset := token.NewFileSet()
	content, err := os.ReadFile("solution.go")
	if err != nil {
		t.Skipf("Cannot read solution.go: %v", err)
		return
	}

	file, err := parser.ParseFile(fset, "solution.go", content, 0)
	if err != nil {
		t.Skipf("Cannot parse solution.go: %v", err)
		return
	}

	functionCount := 0
	helperCount := 0
	for _, decl := range file.Decls {
		if fn, ok := decl.(*ast.FuncDecl); ok {
			functionCount++
			if fn.Name.Name != "ProcessRecords" && fn.Recv == nil {
				helperCount++
			}
		}
	}

	if helperCount < 1 {
		t.Errorf("Expected at least 1 helper function, found %d", helperCount)
	}
}

func TestNoDuplicatedLoops(t *testing.T) {
	fset := token.NewFileSet()
	content, err := os.ReadFile("solution.go")
	if err != nil {
		t.Skipf("Cannot read solution.go: %v", err)
		return
	}

	file, err := parser.ParseFile(fset, "solution.go", content, 0)
	if err != nil {
		t.Skipf("Cannot parse solution.go: %v", err)
		return
	}

	loopCount := 0
	ast.Inspect(file, func(n ast.Node) bool {
		if fn, ok := n.(*ast.FuncDecl); ok {
			if fn.Name.Name == "ProcessRecords" {
				ast.Inspect(fn.Body, func(inner ast.Node) bool {
					if _, ok := inner.(*ast.RangeStmt); ok {
						loopCount++
					}
					return true
				})
				return false
			}
		}
		return true
	})

	if loopCount > 1 {
		t.Errorf("ProcessRecords contains %d loops, expected <= 1 (should use helper functions)", loopCount)
	}
}
