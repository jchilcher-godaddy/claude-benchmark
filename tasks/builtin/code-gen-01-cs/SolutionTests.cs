using Xunit;
using System;

public class FibonacciTests
{
    [Fact]
    public void BaseCaseZero()
    {
        Assert.Equal(0, Fibonacci.Calculate(0));
    }

    [Fact]
    public void BaseCaseOne()
    {
        Assert.Equal(1, Fibonacci.Calculate(1));
    }

    [Fact]
    public void SmallFibonacci()
    {
        Assert.Equal(55, Fibonacci.Calculate(10));
    }

    [Fact]
    public void LargerFibonacci()
    {
        Assert.Equal(6765, Fibonacci.Calculate(20));
    }

    [Fact]
    public void NegativeThrows()
    {
        Assert.Throws<ArgumentException>(() => Fibonacci.Calculate(-1));
    }

    [Fact]
    public void LargeFibonacci()
    {
        Assert.Equal(12586269025L, Fibonacci.Calculate(50));
    }

    [Fact]
    public void SequenceConsistency()
    {
        for (int n = 2; n < 15; n++)
        {
            Assert.Equal(Fibonacci.Calculate(n),
                Fibonacci.Calculate(n - 1) + Fibonacci.Calculate(n - 2));
        }
    }

    [Fact]
    public void SmallValues()
    {
        Assert.Equal(1, Fibonacci.Calculate(2));
        Assert.Equal(2, Fibonacci.Calculate(3));
        Assert.Equal(3, Fibonacci.Calculate(4));
        Assert.Equal(5, Fibonacci.Calculate(5));
        Assert.Equal(8, Fibonacci.Calculate(6));
        Assert.Equal(13, Fibonacci.Calculate(7));
    }

    [Fact]
    public void VeryLarge()
    {
        Assert.Equal(2880067194370816120L, Fibonacci.Calculate(90));
    }

    [Theory]
    [InlineData(-5)]
    [InlineData(-100)]
    public void NegativeVarious(int n)
    {
        Assert.Throws<ArgumentException>(() => Fibonacci.Calculate(n));
    }

    [Fact]
    public void Fibonacci30()
    {
        Assert.Equal(832040, Fibonacci.Calculate(30));
    }
}
