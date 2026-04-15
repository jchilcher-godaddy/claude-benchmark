using System.Collections.Generic;
using System.Linq;

public class OrderItem
{
    public double Price { get; set; }
    public int Quantity { get; set; }
}

public class Order
{
    public List<OrderItem>? Items { get; set; }
    public string? CustomerType { get; set; }
    public string? CouponCode { get; set; }
}

public class OrderResult
{
    public bool Valid { get; set; }
    public string? Error { get; set; }
    public double Subtotal { get; set; }
    public double Discount { get; set; }
    public double Total { get; set; }
}

public static class OrderProcessor
{
    public static OrderResult ValidateAndProcessOrder(Order order)
    {
        if (order.Items == null)
            return new OrderResult { Valid = false, Error = "Order must have items field" };

        if (order.Items.Count == 0)
            return new OrderResult { Valid = false, Error = "Order must contain at least one item" };

        if (order.Items.Any(item => item.Quantity <= 0))
            return new OrderResult { Valid = false, Error = "Item quantities must be positive" };

        if (order.Items.Any(item => item.Price < 0))
            return new OrderResult { Valid = false, Error = "Item prices must be non-negative" };

        double subtotal = order.Items.Sum(item => item.Price * item.Quantity);
        double discount = 0;

        if (order.CustomerType == "premium")
            discount = subtotal * 0.15;
        else if (order.CustomerType == "regular")
            discount = subtotal * 0.05;

        if (order.CouponCode == "SAVE20")
            discount = System.Math.Max(discount, subtotal * 0.20);
        else if (order.CouponCode == "SAVE10")
            discount = System.Math.Max(discount, subtotal * 0.10);

        double total = subtotal - discount;

        return new OrderResult
        {
            Valid = true,
            Subtotal = subtotal,
            Discount = discount,
            Total = total
        };
    }
}
