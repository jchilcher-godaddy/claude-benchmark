using Xunit;
using System.Collections.Generic;
using System.IO;
using System.Linq;

public class OrderProcessorTests
{
    [Fact]
    public void ValidOrderBasic()
    {
        var order = new Order
        {
            Items = new List<OrderItem>
            {
                new OrderItem { Price = 10, Quantity = 2 }
            }
        };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.True(result.Valid);
        Assert.Equal(20, result.Subtotal);
    }

    [Fact]
    public void MissingItems()
    {
        var order = new Order { Items = null };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.False(result.Valid);
        Assert.Contains("items field", result.Error);
    }

    [Fact]
    public void EmptyItems()
    {
        var order = new Order { Items = new List<OrderItem>() };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.False(result.Valid);
        Assert.Contains("at least one item", result.Error);
    }

    [Fact]
    public void InvalidQuantity()
    {
        var order = new Order
        {
            Items = new List<OrderItem>
            {
                new OrderItem { Price = 10, Quantity = 0 }
            }
        };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.False(result.Valid);
        Assert.Contains("quantities must be positive", result.Error);
    }

    [Fact]
    public void NegativePrice()
    {
        var order = new Order
        {
            Items = new List<OrderItem>
            {
                new OrderItem { Price = -10, Quantity = 1 }
            }
        };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.False(result.Valid);
        Assert.Contains("prices must be non-negative", result.Error);
    }

    [Fact]
    public void PremiumCustomerDiscount()
    {
        var order = new Order
        {
            Items = new List<OrderItem>
            {
                new OrderItem { Price = 100, Quantity = 1 }
            },
            CustomerType = "premium"
        };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.True(result.Valid);
        Assert.Equal(15, result.Discount);
        Assert.Equal(85, result.Total);
    }

    [Fact]
    public void RegularCustomerDiscount()
    {
        var order = new Order
        {
            Items = new List<OrderItem>
            {
                new OrderItem { Price = 100, Quantity = 1 }
            },
            CustomerType = "regular"
        };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.True(result.Valid);
        Assert.Equal(5, result.Discount);
        Assert.Equal(95, result.Total);
    }

    [Fact]
    public void CouponCodeSave20()
    {
        var order = new Order
        {
            Items = new List<OrderItem>
            {
                new OrderItem { Price = 100, Quantity = 1 }
            },
            CouponCode = "SAVE20"
        };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.True(result.Valid);
        Assert.Equal(20, result.Discount);
        Assert.Equal(80, result.Total);
    }

    [Fact]
    public void CouponOverridesCustomerType()
    {
        var order = new Order
        {
            Items = new List<OrderItem>
            {
                new OrderItem { Price = 100, Quantity = 1 }
            },
            CustomerType = "premium",
            CouponCode = "SAVE20"
        };
        var result = OrderProcessor.ValidateAndProcessOrder(order);
        Assert.True(result.Valid);
        Assert.Equal(20, result.Discount);
    }

    [Fact]
    public void StructuralTest_MaxNestingDepth()
    {
        var solutionFile = "Solution.cs";
        if (!File.Exists(solutionFile))
        {
            Assert.Fail("Solution.cs not found");
            return;
        }

        var content = File.ReadAllText(solutionFile);
        var lines = content.Split('\n');

        int maxNesting = 0;
        int currentNesting = 0;

        foreach (var line in lines)
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("{"))
                currentNesting++;
            if (trimmed.StartsWith("}"))
                currentNesting--;
            maxNesting = System.Math.Max(maxNesting, currentNesting);
        }

        Assert.True(maxNesting <= 4, $"Expected max nesting depth <= 4, found {maxNesting}");
    }

    [Fact]
    public void StructuralTest_HasEarlyReturns()
    {
        var solutionFile = "Solution.cs";
        if (!File.Exists(solutionFile))
        {
            Assert.Fail("Solution.cs not found");
            return;
        }

        var content = File.ReadAllText(solutionFile);
        var returnCount = System.Text.RegularExpressions.Regex.Matches(content, @"\breturn\b").Count;

        Assert.True(returnCount >= 4, "Expected multiple early returns for guard clauses");
    }
}
