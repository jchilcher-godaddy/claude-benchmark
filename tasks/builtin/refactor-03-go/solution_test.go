package solution

import (
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"strings"
	"testing"
)

func TestBasicProcessing(t *testing.T) {
	input := "alice,sales,100\nbob,engineering,200"
	output := ProcessData(input)
	if strings.Contains(output, "ERROR") {
		t.Errorf("Valid input produced error: %s", output)
	}
	if !strings.Contains(output, "ALICE") || !strings.Contains(output, "BOB") {
		t.Error("Text columns should be uppercased")
	}
	if !strings.Contains(output, "150.00") || !strings.Contains(output, "300.00") {
		t.Error("Derived column should contain multiplied values (1.5x)")
	}
}

func TestEmptyInput(t *testing.T) {
	output := ProcessData("")
	if !strings.Contains(output, "ERROR") || !strings.Contains(output, "No data") {
		t.Errorf("Empty input should produce 'No data' error, got: %s", output)
	}
}

func TestInvalidColumnCount(t *testing.T) {
	input := "alice,sales"
	output := ProcessData(input)
	if !strings.Contains(output, "ERROR") || !strings.Contains(output, "columns") {
		t.Errorf("Invalid column count should produce error, got: %s", output)
	}
}

func TestInvalidNumericValue(t *testing.T) {
	input := "alice,sales,notanumber"
	output := ProcessData(input)
	if !strings.Contains(output, "ERROR") || !strings.Contains(output, "valid number") {
		t.Errorf("Invalid numeric value should produce error, got: %s", output)
	}
}

func TestMultipleRows(t *testing.T) {
	input := "alice,sales,100\nbob,engineering,200\ncharlie,marketing,150"
	output := ProcessData(input)
	if strings.Contains(output, "ERROR") {
		t.Errorf("Valid input produced error: %s", output)
	}
	lines := strings.Split(output, "\n")
	if len(lines) != 3 {
		t.Errorf("Expected 3 output lines, got %d", len(lines))
	}
}

func TestTextNormalization(t *testing.T) {
	input := "Alice,Sales,100"
	output := ProcessData(input)
	if !strings.Contains(output, "ALICE") {
		t.Error("Name should be uppercased")
	}
	if !strings.Contains(output, "SALES") {
		t.Error("Category should be uppercased")
	}
}

func TestDerivedColumnCalculation(t *testing.T) {
	input := "alice,sales,100"
	output := ProcessData(input)
	if !strings.Contains(output, "150.00") {
		t.Error("Derived column should contain 100 * 1.5 = 150.00")
	}
}

func TestFormatting(t *testing.T) {
	input := "alice,sales,100"
	output := ProcessData(input)
	if !strings.Contains(output, "|") {
		t.Error("Output should contain pipe separators")
	}
}

func TestWhitespaceHandling(t *testing.T) {
	input := "  alice  ,  sales  ,  100  "
	output := ProcessData(input)
	if strings.Contains(output, "ERROR") {
		t.Errorf("Input with whitespace should be valid: %s", output)
	}
}

func TestMultipleErrorsReported(t *testing.T) {
	input := "alice,sales\nbob,engineering"
	output := ProcessData(input)
	if !strings.Contains(output, "ERROR") {
		t.Errorf("Invalid rows should produce error: %s", output)
	}
}

func TestStructsExist(t *testing.T) {
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

	structCount := 0
	for _, decl := range file.Decls {
		if gen, ok := decl.(*ast.GenDecl); ok {
			for _, spec := range gen.Specs {
				if _, ok := spec.(*ast.TypeSpec); ok {
					structCount++
				}
			}
		}
	}

	if structCount < 2 {
		t.Errorf("Expected at least 2 structs for separation of concerns, found %d", structCount)
	}
}

func TestMethodsExist(t *testing.T) {
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

	methodCount := 0
	for _, decl := range file.Decls {
		if fn, ok := decl.(*ast.FuncDecl); ok {
			if fn.Recv != nil {
				methodCount++
			}
		}
	}

	if methodCount < 2 {
		t.Errorf("Expected at least 2 methods (struct methods), found %d", methodCount)
	}
}

func TestNoLongFunctionChains(t *testing.T) {
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

	for _, decl := range file.Decls {
		if fn, ok := decl.(*ast.FuncDecl); ok {
			if fn.Name.Name == "ProcessData" {
				ast.Inspect(fn.Body, func(n ast.Node) bool {
					if call, ok := n.(*ast.CallExpr); ok {
						if len(call.Args) > 4 {
							t.Errorf("Function call with %d arguments in ProcessData - should use struct fields instead of long arg chains", len(call.Args))
						}
					}
					return true
				})
			}
		}
	}
}

func TestSeparationOfConcerns(t *testing.T) {
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

	structNames := []string{}
	for _, decl := range file.Decls {
		if gen, ok := decl.(*ast.GenDecl); ok {
			for _, spec := range gen.Specs {
				if ts, ok := spec.(*ast.TypeSpec); ok {
					if _, ok := ts.Type.(*ast.StructType); ok {
						structNames = append(structNames, ts.Name.Name)
					}
				}
			}
		}
	}

	concernKeywords := []string{"Parse", "Validat", "Transform", "Format"}
	foundConcerns := 0
	for _, name := range structNames {
		for _, keyword := range concernKeywords {
			if strings.Contains(name, keyword) {
				foundConcerns++
				break
			}
		}
	}

	if foundConcerns < 2 {
		t.Errorf("Expected structs representing different concerns (parsing, validation, transformation, formatting), found %d", foundConcerns)
	}
}
