package solution

import (
	"strings"
	"testing"
)

func TestMergeSimple(t *testing.T) {
	base := map[string]interface{}{"a": 1}
	overlay := map[string]interface{}{"b": 2}
	result, err := MergeConfigs(base, overlay)
	if err != nil {
		t.Fatalf("MergeConfigs error: %v", err)
	}
	if result["a"] != 1 || result["b"] != 2 {
		t.Errorf("result = %v, want {a:1, b:2}", result)
	}
}

func TestMergeOverride(t *testing.T) {
	base := map[string]interface{}{"a": 1}
	overlay := map[string]interface{}{"a": 2}
	result, err := MergeConfigs(base, overlay)
	if err != nil {
		t.Fatalf("MergeConfigs error: %v", err)
	}
	if result["a"] != 2 {
		t.Errorf("result[a] = %v, want 2", result["a"])
	}
}

func TestMergeNested(t *testing.T) {
	base := map[string]interface{}{"nested": map[string]interface{}{"a": 1}}
	overlay := map[string]interface{}{"nested": map[string]interface{}{"b": 2}}
	result, err := MergeConfigs(base, overlay)
	if err != nil {
		t.Fatalf("MergeConfigs error: %v", err)
	}
	nested := result["nested"].(map[string]interface{})
	if nested["a"] != 1 || nested["b"] != 2 {
		t.Errorf("nested = %v, want {a:1, b:2}", nested)
	}
}

func TestMergeDelete(t *testing.T) {
	base := map[string]interface{}{"a": 1, "b": 2}
	overlay := map[string]interface{}{"a": "__delete__"}
	result, err := MergeConfigs(base, overlay)
	if err != nil {
		t.Fatalf("MergeConfigs error: %v", err)
	}
	if _, exists := result["a"]; exists {
		t.Error("expected key 'a' to be deleted")
	}
	if result["b"] != 2 {
		t.Errorf("result[b] = %v, want 2", result["b"])
	}
}

func TestMergeTypeConflict(t *testing.T) {
	base := map[string]interface{}{"key": map[string]interface{}{"nested": 1}}
	overlay := map[string]interface{}{"key": "scalar"}
	_, err := MergeConfigs(base, overlay)
	if err == nil {
		t.Error("expected error for type conflict")
	}
	if !strings.Contains(err.Error(), "conflict") && !strings.Contains(err.Error(), "Type") {
		t.Errorf("error = %q, want mention of conflict or Type", err.Error())
	}
}

func TestMergeNoMutation(t *testing.T) {
	base := map[string]interface{}{"a": 1}
	overlay := map[string]interface{}{"b": 2}
	MergeConfigs(base, overlay)
	if len(base) != 1 || base["a"] != 1 {
		t.Error("base was mutated")
	}
	if len(overlay) != 1 || overlay["b"] != 2 {
		t.Error("overlay was mutated")
	}
}

func TestMergeMultipleOverlays(t *testing.T) {
	base := map[string]interface{}{"a": 1}
	overlay1 := map[string]interface{}{"b": 2}
	overlay2 := map[string]interface{}{"c": 3}
	result, err := MergeConfigs(base, overlay1, overlay2)
	if err != nil {
		t.Fatalf("MergeConfigs error: %v", err)
	}
	if result["a"] != 1 || result["b"] != 2 || result["c"] != 3 {
		t.Errorf("result = %v, want {a:1, b:2, c:3}", result)
	}
}

func TestValidateValid(t *testing.T) {
	merged := map[string]interface{}{"port": 8080, "host": "localhost"}
	schema := map[string]interface{}{"port": "int", "host": "string"}
	violations := ValidateConfig(merged, schema)
	if len(violations) != 0 {
		t.Errorf("violations = %v, want empty", violations)
	}
}

func TestValidateMissingKey(t *testing.T) {
	merged := map[string]interface{}{"port": 8080}
	schema := map[string]interface{}{"port": "int", "host": "string"}
	violations := ValidateConfig(merged, schema)
	if len(violations) == 0 {
		t.Error("expected violations for missing key")
	}
	found := false
	for _, v := range violations {
		if strings.Contains(v, "host") && strings.Contains(v, "Missing") {
			found = true
		}
	}
	if !found {
		t.Errorf("violations = %v, want mention of missing 'host'", violations)
	}
}

func TestValidateTypeMismatch(t *testing.T) {
	merged := map[string]interface{}{"port": "8080"}
	schema := map[string]interface{}{"port": "int"}
	violations := ValidateConfig(merged, schema)
	if len(violations) == 0 {
		t.Error("expected violations for type mismatch")
	}
	found := false
	for _, v := range violations {
		if strings.Contains(v, "port") && strings.Contains(v, "mismatch") {
			found = true
		}
	}
	if !found {
		t.Errorf("violations = %v, want mention of type mismatch at 'port'", violations)
	}
}

func TestValidateNested(t *testing.T) {
	merged := map[string]interface{}{
		"server": map[string]interface{}{
			"port": 8080,
			"host": "localhost",
		},
	}
	schema := map[string]interface{}{
		"server": map[string]interface{}{
			"port": "int",
			"host": "string",
		},
	}
	violations := ValidateConfig(merged, schema)
	if len(violations) != 0 {
		t.Errorf("violations = %v, want empty", violations)
	}
}

func TestValidateNestedMissing(t *testing.T) {
	merged := map[string]interface{}{
		"server": map[string]interface{}{
			"port": 8080,
		},
	}
	schema := map[string]interface{}{
		"server": map[string]interface{}{
			"port": "int",
			"host": "string",
		},
	}
	violations := ValidateConfig(merged, schema)
	if len(violations) == 0 {
		t.Error("expected violations for missing nested key")
	}
}

func TestMergeListReplacement(t *testing.T) {
	base := map[string]interface{}{"items": []int{1, 2, 3}}
	overlay := map[string]interface{}{"items": []int{4, 5}}
	result, err := MergeConfigs(base, overlay)
	if err != nil {
		t.Fatalf("MergeConfigs error: %v", err)
	}
	items := result["items"].([]int)
	if len(items) != 2 || items[0] != 4 || items[1] != 5 {
		t.Errorf("items = %v, want [4, 5]", items)
	}
}

func TestValidateBoolType(t *testing.T) {
	merged := map[string]interface{}{"enabled": true}
	schema := map[string]interface{}{"enabled": "bool"}
	violations := ValidateConfig(merged, schema)
	if len(violations) != 0 {
		t.Errorf("violations = %v, want empty", violations)
	}
}

func TestValidateFloat64Type(t *testing.T) {
	merged := map[string]interface{}{"ratio": 3.14}
	schema := map[string]interface{}{"ratio": "float64"}
	violations := ValidateConfig(merged, schema)
	if len(violations) != 0 {
		t.Errorf("violations = %v, want empty", violations)
	}
}

func TestMergeDeepNesting(t *testing.T) {
	base := map[string]interface{}{
		"level1": map[string]interface{}{
			"level2": map[string]interface{}{
				"level3": map[string]interface{}{
					"value": 1,
				},
			},
		},
	}
	overlay := map[string]interface{}{
		"level1": map[string]interface{}{
			"level2": map[string]interface{}{
				"level3": map[string]interface{}{
					"value": 2,
				},
			},
		},
	}
	result, err := MergeConfigs(base, overlay)
	if err != nil {
		t.Fatalf("MergeConfigs error: %v", err)
	}
	value := result["level1"].(map[string]interface{})["level2"].(map[string]interface{})["level3"].(map[string]interface{})["value"]
	if value != 2 {
		t.Errorf("deep nested value = %v, want 2", value)
	}
}
