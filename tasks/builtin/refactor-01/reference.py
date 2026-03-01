"""Process customer records with various aggregations."""


def _sum_amounts_by_field(records: list[dict], field: str, value: str) -> float:
    """Sum amounts for records matching a field value.

    Args:
        records: List of customer record dicts
        field: Field name to filter on
        value: Value to match

    Returns:
        Total amount for matching records
    """
    total = 0
    for record in records:
        if record.get(field) == value and "amount" in record:
            amount = record["amount"]
            if amount > 0:
                total += amount
    return total


def _count_records_by_fields(
    records: list[dict], filters: dict[str, str]
) -> int:
    """Count records matching all filter criteria.

    Args:
        records: List of customer record dicts
        filters: Dict of field->value pairs that must all match

    Returns:
        Count of matching records
    """
    count = 0
    for record in records:
        if all(record.get(field) == value for field, value in filters.items()):
            count += 1
    return count


def process_records(records: list[dict]) -> dict:
    """Process customer records and compute various statistics.

    Args:
        records: List of customer record dicts with 'status', 'amount', 'priority' fields

    Returns:
        Dict with active_total, high_priority_total, and pending_total
    """
    return {
        "active_total": _sum_amounts_by_field(records, "status", "active"),
        "high_priority_total": _sum_amounts_by_field(records, "priority", "high"),
        "pending_total": _sum_amounts_by_field(records, "status", "pending"),
        "active_high_priority_count": _count_records_by_fields(
            records, {"status": "active", "priority": "high"}
        ),
        "pending_high_priority_count": _count_records_by_fields(
            records, {"status": "pending", "priority": "high"}
        ),
    }
