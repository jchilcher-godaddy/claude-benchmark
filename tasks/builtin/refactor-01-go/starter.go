package solution

type Record map[string]interface{}

type Result struct {
	ActiveTotal               float64
	HighPriorityTotal         float64
	PendingTotal              float64
	ActiveHighPriorityCount   int
	PendingHighPriorityCount  int
}

func ProcessRecords(records []Record) Result {
	activeTotal := 0.0
	for _, record := range records {
		if status, ok := record["status"].(string); ok && status == "active" {
			if amount, ok := record["amount"].(float64); ok && amount > 0 {
				activeTotal += amount
			}
		}
	}

	highPriorityTotal := 0.0
	for _, record := range records {
		if priority, ok := record["priority"].(string); ok && priority == "high" {
			if amount, ok := record["amount"].(float64); ok && amount > 0 {
				highPriorityTotal += amount
			}
		}
	}

	pendingTotal := 0.0
	for _, record := range records {
		if status, ok := record["status"].(string); ok && status == "pending" {
			if amount, ok := record["amount"].(float64); ok && amount > 0 {
				pendingTotal += amount
			}
		}
	}

	activeHighPriorityCount := 0
	for _, record := range records {
		if status, ok := record["status"].(string); ok && status == "active" {
			if priority, ok := record["priority"].(string); ok && priority == "high" {
				activeHighPriorityCount++
			}
		}
	}

	pendingHighPriorityCount := 0
	for _, record := range records {
		if status, ok := record["status"].(string); ok && status == "pending" {
			if priority, ok := record["priority"].(string); ok && priority == "high" {
				pendingHighPriorityCount++
			}
		}
	}

	return Result{
		ActiveTotal:              activeTotal,
		HighPriorityTotal:        highPriorityTotal,
		PendingTotal:             pendingTotal,
		ActiveHighPriorityCount:  activeHighPriorityCount,
		PendingHighPriorityCount: pendingHighPriorityCount,
	}
}
