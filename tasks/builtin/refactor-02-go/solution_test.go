package solution

import (
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"testing"
)

func TestValidOrder(t *testing.T) {
	order := Order{
		Items: []Item{
			{Price: 10.0, Quantity: 2},
			{Price: 5.0, Quantity: 3},
		},
		CustomerType: "regular",
	}
	result := ValidateAndProcessOrder(order)
	if !result.Valid {
		t.Errorf("Valid order rejected: %s", result.Error)
	}
	if result.Subtotal != 35.0 {
		t.Errorf("Subtotal = %f, want 35.0", result.Subtotal)
	}
}

func TestEmptyItems(t *testing.T) {
	order := Order{Items: []Item{}}
	result := ValidateAndProcessOrder(order)
	if result.Valid {
		t.Error("Empty order should be invalid")
	}
	if result.Error == "" {
		t.Error("Error message should be set")
	}
}

func TestNegativeQuantity(t *testing.T) {
	order := Order{
		Items: []Item{{Price: 10.0, Quantity: -1}},
	}
	result := ValidateAndProcessOrder(order)
	if result.Valid {
		t.Error("Order with negative quantity should be invalid")
	}
}

func TestZeroQuantity(t *testing.T) {
	order := Order{
		Items: []Item{{Price: 10.0, Quantity: 0}},
	}
	result := ValidateAndProcessOrder(order)
	if result.Valid {
		t.Error("Order with zero quantity should be invalid")
	}
}

func TestNegativePrice(t *testing.T) {
	order := Order{
		Items: []Item{{Price: -10.0, Quantity: 1}},
	}
	result := ValidateAndProcessOrder(order)
	if result.Valid {
		t.Error("Order with negative price should be invalid")
	}
}

func TestPremiumDiscount(t *testing.T) {
	order := Order{
		Items:        []Item{{Price: 100.0, Quantity: 1}},
		CustomerType: "premium",
	}
	result := ValidateAndProcessOrder(order)
	if !result.Valid {
		t.Fatalf("Valid order rejected: %s", result.Error)
	}
	if result.Discount != 15.0 {
		t.Errorf("Premium discount = %f, want 15.0", result.Discount)
	}
	if result.Total != 85.0 {
		t.Errorf("Total = %f, want 85.0", result.Total)
	}
}

func TestRegularDiscount(t *testing.T) {
	order := Order{
		Items:        []Item{{Price: 100.0, Quantity: 1}},
		CustomerType: "regular",
	}
	result := ValidateAndProcessOrder(order)
	if !result.Valid {
		t.Fatalf("Valid order rejected: %s", result.Error)
	}
	if result.Discount != 5.0 {
		t.Errorf("Regular discount = %f, want 5.0", result.Discount)
	}
	if result.Total != 95.0 {
		t.Errorf("Total = %f, want 95.0", result.Total)
	}
}

func TestCouponSAVE20(t *testing.T) {
	order := Order{
		Items:      []Item{{Price: 100.0, Quantity: 1}},
		CouponCode: "SAVE20",
	}
	result := ValidateAndProcessOrder(order)
	if !result.Valid {
		t.Fatalf("Valid order rejected: %s", result.Error)
	}
	if result.Discount != 20.0 {
		t.Errorf("SAVE20 discount = %f, want 20.0", result.Discount)
	}
}

func TestCouponSAVE10(t *testing.T) {
	order := Order{
		Items:      []Item{{Price: 100.0, Quantity: 1}},
		CouponCode: "SAVE10",
	}
	result := ValidateAndProcessOrder(order)
	if !result.Valid {
		t.Fatalf("Valid order rejected: %s", result.Error)
	}
	if result.Discount != 10.0 {
		t.Errorf("SAVE10 discount = %f, want 10.0", result.Discount)
	}
}

func TestCouponOverridesCustomerType(t *testing.T) {
	order := Order{
		Items:        []Item{{Price: 100.0, Quantity: 1}},
		CustomerType: "regular",
		CouponCode:   "SAVE20",
	}
	result := ValidateAndProcessOrder(order)
	if !result.Valid {
		t.Fatalf("Valid order rejected: %s", result.Error)
	}
	if result.Discount != 20.0 {
		t.Errorf("Discount = %f, want 20.0 (coupon should override customer discount)", result.Discount)
	}
}

func TestMultipleItems(t *testing.T) {
	order := Order{
		Items: []Item{
			{Price: 10.0, Quantity: 2},
			{Price: 20.0, Quantity: 1},
			{Price: 5.0, Quantity: 4},
		},
	}
	result := ValidateAndProcessOrder(order)
	if !result.Valid {
		t.Fatalf("Valid order rejected: %s", result.Error)
	}
	expected := 10.0*2 + 20.0*1 + 5.0*4
	if result.Subtotal != expected {
		t.Errorf("Subtotal = %f, want %f", result.Subtotal, expected)
	}
}

func TestNestingDepth(t *testing.T) {
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

	maxDepth := 0
	for _, decl := range file.Decls {
		if fn, ok := decl.(*ast.FuncDecl); ok {
			if fn.Name.Name == "ValidateAndProcessOrder" {
				maxDepth = measureNestingDepth(fn.Body, 0)
				break
			}
		}
	}

	if maxDepth > 3 {
		t.Errorf("Maximum nesting depth = %d, want <= 3", maxDepth)
	}
}

func measureNestingDepth(node ast.Node, currentDepth int) int {
	if node == nil {
		return currentDepth
	}

	maxDepth := currentDepth
	ast.Inspect(node, func(n ast.Node) bool {
		switch n.(type) {
		case *ast.IfStmt, *ast.ForStmt, *ast.RangeStmt, *ast.SwitchStmt, *ast.SelectStmt:
			depth := measureNestingDepth(n, currentDepth+1)
			if depth > maxDepth {
				maxDepth = depth
			}
			return false
		}
		return true
	})

	return maxDepth
}

func TestEarlyReturnsUsed(t *testing.T) {
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

	returnCount := 0
	for _, decl := range file.Decls {
		if fn, ok := decl.(*ast.FuncDecl); ok {
			if fn.Name.Name == "ValidateAndProcessOrder" {
				ast.Inspect(fn.Body, func(n ast.Node) bool {
					if _, ok := n.(*ast.ReturnStmt); ok {
						returnCount++
					}
					return true
				})
				break
			}
		}
	}

	if returnCount < 3 {
		t.Errorf("Return statement count = %d, want >= 3 (should use early returns)", returnCount)
	}
}
