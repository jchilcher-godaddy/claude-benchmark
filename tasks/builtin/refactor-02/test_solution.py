"""Tests for refactor-02 task."""

import ast
import pytest
from pathlib import Path

from solution import validate_and_process_order


def test_valid_order_no_discount():
    """Test valid order without discounts."""
    order = {
        "items": [
            {"price": 10.0, "quantity": 2},
            {"price": 5.0, "quantity": 3},
        ]
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 35.0
    assert result["discount"] == 0
    assert result["total"] == 35.0


def test_valid_order_with_premium_customer():
    """Test valid order with premium customer discount."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "customer_type": "premium",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 100.0
    assert result["discount"] == 15.0
    assert result["total"] == 85.0


def test_valid_order_with_regular_customer():
    """Test valid order with regular customer discount."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "customer_type": "regular",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 100.0
    assert result["discount"] == 5.0
    assert result["total"] == 95.0


def test_valid_order_with_save20_coupon():
    """Test valid order with SAVE20 coupon."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "coupon_code": "SAVE20",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 100.0
    assert result["discount"] == 20.0
    assert result["total"] == 80.0


def test_valid_order_with_save10_coupon():
    """Test valid order with SAVE10 coupon."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "coupon_code": "SAVE10",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 100.0
    assert result["discount"] == 10.0
    assert result["total"] == 90.0


def test_coupon_overrides_lower_customer_discount():
    """Test that higher coupon discount overrides lower customer discount."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "customer_type": "regular",
        "coupon_code": "SAVE20",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["discount"] == 20.0


def test_customer_discount_used_when_higher_than_coupon():
    """Test that customer discount is used when higher than coupon."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "customer_type": "premium",
        "coupon_code": "SAVE10",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["discount"] == 15.0


def test_missing_items_field():
    """Test order missing items field."""
    order = {"customer_type": "regular"}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Order must have items field"


def test_empty_items():
    """Test order with empty items list."""
    order = {"items": []}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Order must contain at least one item"


def test_items_not_dicts():
    """Test order with non-dict items."""
    order = {"items": ["item1", "item2"]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Items must be dictionaries"


def test_items_missing_price():
    """Test order with items missing price."""
    order = {"items": [{"quantity": 1}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Items must have price and quantity"


def test_items_missing_quantity():
    """Test order with items missing quantity."""
    order = {"items": [{"price": 10.0}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Items must have price and quantity"


def test_zero_quantity():
    """Test order with zero quantity."""
    order = {"items": [{"price": 10.0, "quantity": 0}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Item quantities must be positive"


def test_negative_quantity():
    """Test order with negative quantity."""
    order = {"items": [{"price": 10.0, "quantity": -1}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Item quantities must be positive"


def test_negative_price():
    """Test order with negative price."""
    order = {"items": [{"price": -10.0, "quantity": 1}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Item prices must be non-negative"


def test_zero_price():
    """Test order with zero price (should be valid)."""
    order = {"items": [{"price": 0.0, "quantity": 1}]}
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 0.0


def test_multiple_items():
    """Test order with multiple items and complex pricing."""
    order = {
        "items": [
            {"price": 10.0, "quantity": 2},
            {"price": 15.0, "quantity": 1},
            {"price": 5.0, "quantity": 4},
        ],
        "customer_type": "premium",
        "coupon_code": "SAVE10",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 55.0
    assert result["discount"] == 8.25
    assert result["total"] == 46.75


def _calculate_nesting_depth(node, current_depth=0):
    """Calculate maximum nesting depth of control flow structures."""
    max_depth = current_depth

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            child_depth = _calculate_nesting_depth(child, current_depth + 1)
            max_depth = max(max_depth, child_depth)
        else:
            child_depth = _calculate_nesting_depth(child, current_depth)
            max_depth = max(max_depth, child_depth)

    return max_depth


def test_max_nesting_depth():
    """Verify solution reduces excessive nesting using early returns.

    The starter code has deep nesting (6+ levels of if statements).
    A properly refactored solution should have max nesting depth <= 3.
    """
    solution_path = Path(__file__).parent / "solution.py"
    with open(solution_path) as f:
        tree = ast.parse(f.read())

    max_depth = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "validate_and_process_order":
            depth = _calculate_nesting_depth(node)
            max_depth = max(max_depth, depth)

    assert max_depth <= 3, (
        f"Expected max nesting depth <= 3 (found {max_depth}). "
        "The task requires flattening nested conditionals using early returns."
    )


def test_uses_early_returns():
    """Verify solution uses early return pattern to reduce nesting.

    The task requires replacing deeply nested conditionals with early returns.
    Check that Return nodes exist at shallow depths (depth <= 2) in the function.
    """
    solution_path = Path(__file__).parent / "solution.py"
    with open(solution_path) as f:
        tree = ast.parse(f.read())

    def find_early_returns(node, depth=0):
        """Find return statements and their nesting depths."""
        returns = []
        if isinstance(node, ast.Return):
            returns.append(depth)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                returns.extend(find_early_returns(child, depth + 1))
            else:
                returns.extend(find_early_returns(child, depth))
        return returns

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "validate_and_process_order":
            return_depths = find_early_returns(node)
            shallow_returns = [d for d in return_depths if d <= 2]

            assert len(shallow_returns) >= 3, (
                f"Expected at least 3 early returns at depth <= 2 (found {len(shallow_returns)}). "
                "The task requires using early returns to handle validation errors."
            )
