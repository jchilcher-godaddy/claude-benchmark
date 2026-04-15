package solution

type Item struct {
	Price    float64
	Quantity int
}

type Order struct {
	Items        []Item
	CustomerType string
	CouponCode   string
}

type OrderResult struct {
	Valid    bool
	Error    string
	Subtotal float64
	Discount float64
	Total    float64
}

func ValidateAndProcessOrder(order Order) OrderResult {
	if len(order.Items) > 0 {
		allValid := true
		for _, item := range order.Items {
			if item.Quantity <= 0 {
				allValid = false
				break
			}
		}
		if allValid {
			allPricesValid := true
			for _, item := range order.Items {
				if item.Price < 0 {
					allPricesValid = false
					break
				}
			}
			if allPricesValid {
				subtotal := 0.0
				for _, item := range order.Items {
					subtotal += item.Price * float64(item.Quantity)
				}
				discount := 0.0

				if order.CustomerType != "" {
					if order.CustomerType == "premium" {
						discount = subtotal * 0.15
					} else {
						if order.CustomerType == "regular" {
							discount = subtotal * 0.05
						}
					}
				}

				if order.CouponCode != "" {
					if order.CouponCode == "SAVE20" {
						couponDiscount := subtotal * 0.20
						if couponDiscount > discount {
							discount = couponDiscount
						}
					} else {
						if order.CouponCode == "SAVE10" {
							couponDiscount := subtotal * 0.10
							if couponDiscount > discount {
								discount = couponDiscount
							}
						}
					}
				}

				total := subtotal - discount

				return OrderResult{
					Valid:    true,
					Subtotal: subtotal,
					Discount: discount,
					Total:    total,
				}
			} else {
				return OrderResult{Valid: false, Error: "Item prices must be non-negative"}
			}
		} else {
			return OrderResult{Valid: false, Error: "Item quantities must be positive"}
		}
	} else {
		return OrderResult{Valid: false, Error: "Order must contain at least one item"}
	}
}
