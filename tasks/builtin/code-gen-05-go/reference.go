package solution

import (
	"fmt"
	"reflect"
)

type ConfigMergeError struct {
	Message string
}

func (e *ConfigMergeError) Error() string {
	return e.Message
}

func MergeConfigs(base map[string]interface{}, overlays ...map[string]interface{}) (map[string]interface{}, error) {
	checkCircular := func(m map[string]interface{}, seen map[uintptr]bool) error {
		ptr := reflect.ValueOf(m).Pointer()
		if seen[ptr] {
			return &ConfigMergeError{"Circular reference detected"}
		}
		seen[ptr] = true
		for _, v := range m {
			if subMap, ok := v.(map[string]interface{}); ok {
				if err := checkCircular(subMap, seen); err != nil {
					return err
				}
			}
		}
		return nil
	}

	deepCopy := func(m map[string]interface{}) map[string]interface{} {
		result := make(map[string]interface{})
		for k, v := range m {
			if subMap, ok := v.(map[string]interface{}); ok {
				result[k] = deepCopy(subMap)
			} else {
				result[k] = v
			}
		}
		return result
	}

	var merge func(a, b map[string]interface{}, path string) (map[string]interface{}, error)
	merge = func(a, b map[string]interface{}, path string) (map[string]interface{}, error) {
		result := deepCopy(a)
		for key, bVal := range b {
			currentPath := key
			if path != "" {
				currentPath = path + "." + key
			}

			if strVal, ok := bVal.(string); ok && strVal == "__delete__" {
				delete(result, key)
				continue
			}

			if aVal, exists := result[key]; exists {
				aMap, aIsMap := aVal.(map[string]interface{})
				bMap, bIsMap := bVal.(map[string]interface{})

				if aIsMap && bIsMap {
					merged, err := merge(aMap, bMap, currentPath)
					if err != nil {
						return nil, err
					}
					result[key] = merged
				} else if aIsMap != bIsMap {
					return nil, &ConfigMergeError{
						fmt.Sprintf("Type conflict at %q: cannot merge %s with %s",
							currentPath, reflect.TypeOf(aVal).String(), reflect.TypeOf(bVal).String()),
					}
				} else {
					result[key] = bVal
				}
			} else {
				if subMap, ok := bVal.(map[string]interface{}); ok {
					result[key] = deepCopy(subMap)
				} else {
					result[key] = bVal
				}
			}
		}
		return result, nil
	}

	if err := checkCircular(base, make(map[uintptr]bool)); err != nil {
		return nil, err
	}
	for _, overlay := range overlays {
		if err := checkCircular(overlay, make(map[uintptr]bool)); err != nil {
			return nil, err
		}
	}

	result := deepCopy(base)
	for _, overlay := range overlays {
		var err error
		result, err = merge(result, overlay, "")
		if err != nil {
			return nil, err
		}
	}
	return result, nil
}

func ValidateConfig(merged map[string]interface{}, schema map[string]interface{}) []string {
	var validate func(m, s map[string]interface{}, path string) []string
	validate = func(m, s map[string]interface{}, path string) []string {
		violations := []string{}

		for key, expected := range s {
			currentPath := key
			if path != "" {
				currentPath = path + "." + key
			}

			actual, exists := m[key]
			if !exists {
				violations = append(violations, fmt.Sprintf("Missing required key: %q", currentPath))
				continue
			}

			if schemaMap, ok := expected.(map[string]interface{}); ok {
				actualMap, ok := actual.(map[string]interface{})
				if !ok {
					violations = append(violations, fmt.Sprintf("Type mismatch at %q: expected dict, got %s",
						currentPath, reflect.TypeOf(actual).String()))
				} else {
					violations = append(violations, validate(actualMap, schemaMap, currentPath)...)
				}
			} else if typeName, ok := expected.(string); ok {
				actualType := reflect.TypeOf(actual)
				expectedType := ""
				valid := false

				switch typeName {
				case "string":
					_, valid = actual.(string)
					expectedType = "string"
				case "int":
					_, valid = actual.(int)
					expectedType = "int"
				case "float64":
					_, valid = actual.(float64)
					expectedType = "float64"
				case "bool":
					_, valid = actual.(bool)
					expectedType = "bool"
				case "map":
					_, valid = actual.(map[string]interface{})
					expectedType = "map"
				}

				if !valid {
					violations = append(violations, fmt.Sprintf("Type mismatch at %q: expected %s, got %s",
						currentPath, expectedType, actualType.String()))
				}
			}
		}

		return violations
	}

	return validate(merged, schema, "")
}
