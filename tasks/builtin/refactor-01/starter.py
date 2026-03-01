"""Process customer records with various aggregations."""


def process_records(records: list[dict]) -> dict:
    """Process customer records and compute various statistics.

    Args:
        records: List of customer record dicts with 'status', 'amount', 'priority' fields

    Returns:
        Dict with active_total, high_priority_total, and pending_total
    """
    # Calculate total amount for active customers
    active_total = 0
    for record in records:
        if "status" in record and record["status"] == "active":
            if "amount" in record:
                amount = record["amount"]
                if amount > 0:
                    active_total += amount

    # Calculate total amount for high priority customers
    high_priority_total = 0
    for record in records:
        if "priority" in record and record["priority"] == "high":
            if "amount" in record:
                amount = record["amount"]
                if amount > 0:
                    high_priority_total += amount

    # Calculate total amount for pending customers
    pending_total = 0
    for record in records:
        if "status" in record and record["status"] == "pending":
            if "amount" in record:
                amount = record["amount"]
                if amount > 0:
                    pending_total += amount

    # Calculate count of active high priority customers
    active_high_priority_count = 0
    for record in records:
        if "status" in record and record["status"] == "active":
            if "priority" in record and record["priority"] == "high":
                active_high_priority_count += 1

    # Calculate count of pending high priority customers
    pending_high_priority_count = 0
    for record in records:
        if "status" in record and record["status"] == "pending":
            if "priority" in record and record["priority"] == "high":
                pending_high_priority_count += 1

    return {
        "active_total": active_total,
        "high_priority_total": high_priority_total,
        "pending_total": pending_total,
        "active_high_priority_count": active_high_priority_count,
        "pending_high_priority_count": pending_high_priority_count,
    }
