package solution

type Record map[string]interface{}

type Result struct {
	ActiveTotal              float64
	HighPriorityTotal        float64
	PendingTotal             float64
	ActiveHighPriorityCount  int
	PendingHighPriorityCount int
}

func sumAmountsByField(records []Record, field string, value string) float64 {
	total := 0.0
	for _, record := range records {
		if fieldValue, ok := record[field].(string); ok && fieldValue == value {
			if amount, ok := record["amount"].(float64); ok && amount > 0 {
				total += amount
			}
		}
	}
	return total
}

func countRecordsByFields(records []Record, filters map[string]string) int {
	count := 0
	for _, record := range records {
		matches := true
		for field, value := range filters {
			if fieldValue, ok := record[field].(string); !ok || fieldValue != value {
				matches = false
				break
			}
		}
		if matches {
			count++
		}
	}
	return count
}

func ProcessRecords(records []Record) Result {
	return Result{
		ActiveTotal:       sumAmountsByField(records, "status", "active"),
		HighPriorityTotal: sumAmountsByField(records, "priority", "high"),
		PendingTotal:      sumAmountsByField(records, "status", "pending"),
		ActiveHighPriorityCount: countRecordsByFields(records, map[string]string{
			"status":   "active",
			"priority": "high",
		}),
		PendingHighPriorityCount: countRecordsByFields(records, map[string]string{
			"status":   "pending",
			"priority": "high",
		}),
	}
}
