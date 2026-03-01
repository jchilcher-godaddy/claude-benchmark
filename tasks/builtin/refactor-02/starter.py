"""Order validation and processing with nested conditionals."""


def validate_and_process_order(order: dict) -> dict:
    """Validate and process an order, applying discounts and calculating totals.

    Args:
        order: Order dict with 'items', 'customer_type', 'coupon_code' fields

    Returns:
        Processed order dict with validation status, subtotal, discount, and total
    """
    if "items" in order:
        if order["items"]:
            if all(isinstance(item, dict) for item in order["items"]):
                if all("price" in item and "quantity" in item for item in order["items"]):
                    if all(item["quantity"] > 0 for item in order["items"]):
                        if all(item["price"] >= 0 for item in order["items"]):
                            subtotal = sum(
                                item["price"] * item["quantity"]
                                for item in order["items"]
                            )
                            discount = 0

                            if "customer_type" in order:
                                if order["customer_type"] == "premium":
                                    discount = subtotal * 0.15
                                else:
                                    if order["customer_type"] == "regular":
                                        discount = subtotal * 0.05

                            if "coupon_code" in order:
                                if order["coupon_code"] == "SAVE20":
                                    coupon_discount = subtotal * 0.20
                                    if coupon_discount > discount:
                                        discount = coupon_discount
                                else:
                                    if order["coupon_code"] == "SAVE10":
                                        coupon_discount = subtotal * 0.10
                                        if coupon_discount > discount:
                                            discount = coupon_discount

                            total = subtotal - discount

                            return {
                                "valid": True,
                                "subtotal": subtotal,
                                "discount": discount,
                                "total": total,
                            }
                        else:
                            return {"valid": False, "error": "Item prices must be non-negative"}
                    else:
                        return {"valid": False, "error": "Item quantities must be positive"}
                else:
                    return {"valid": False, "error": "Items must have price and quantity"}
            else:
                return {"valid": False, "error": "Items must be dictionaries"}
        else:
            return {"valid": False, "error": "Order must contain at least one item"}
    else:
        return {"valid": False, "error": "Order must have items field"}
