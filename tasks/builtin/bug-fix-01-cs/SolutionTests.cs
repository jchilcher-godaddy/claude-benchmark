using Xunit;

public class BinarySearchTests
{
    [Fact]
    public void FindsElementInMiddle()
    {
        Assert.Equal(2, BinarySearch.Search(new[] { 1, 3, 5, 7, 9 }, 5));
    }

    [Fact]
    public void FindsFirstElement()
    {
        Assert.Equal(0, BinarySearch.Search(new[] { 1, 3, 5, 7, 9 }, 1));
    }

    [Fact]
    public void FindsLastElement()
    {
        Assert.Equal(4, BinarySearch.Search(new[] { 1, 3, 5, 7, 9 }, 9));
    }

    [Fact]
    public void ReturnsMinusOneWhenNotFound()
    {
        Assert.Equal(-1, BinarySearch.Search(new[] { 1, 3, 5, 7, 9 }, 4));
    }

    [Fact]
    public void EmptyArray()
    {
        Assert.Equal(-1, BinarySearch.Search(new int[] { }, 5));
    }

    [Fact]
    public void SingleElementFound()
    {
        Assert.Equal(0, BinarySearch.Search(new[] { 5 }, 5));
    }

    [Fact]
    public void SingleElementNotFound()
    {
        Assert.Equal(-1, BinarySearch.Search(new[] { 5 }, 3));
    }

    [Fact]
    public void TwoElementsFirstFound()
    {
        Assert.Equal(0, BinarySearch.Search(new[] { 3, 7 }, 3));
    }

    [Fact]
    public void TwoElementsSecondFound()
    {
        Assert.Equal(1, BinarySearch.Search(new[] { 3, 7 }, 7));
    }

    [Fact]
    public void LargerArray()
    {
        var arr = new[] { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 };
        Assert.Equal(7, BinarySearch.Search(arr, 8));
        Assert.Equal(14, BinarySearch.Search(arr, 15));
        Assert.Equal(0, BinarySearch.Search(arr, 1));
    }

    [Fact]
    public void TargetLessThanAll()
    {
        Assert.Equal(-1, BinarySearch.Search(new[] { 5, 10, 15 }, 2));
    }

    [Fact]
    public void TargetGreaterThanAll()
    {
        Assert.Equal(-1, BinarySearch.Search(new[] { 5, 10, 15 }, 20));
    }
}
