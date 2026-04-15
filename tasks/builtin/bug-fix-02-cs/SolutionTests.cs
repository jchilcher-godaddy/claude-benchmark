using Xunit;
using System.Linq;

public class MergeSortTests
{
    [Fact]
    public void EmptyArray()
    {
        var result = MergeSort.Sort(new int[] { });
        Assert.Empty(result);
    }

    [Fact]
    public void SingleElement()
    {
        var result = MergeSort.Sort(new[] { 5 });
        Assert.Equal(new[] { 5 }, result);
    }

    [Fact]
    public void TwoElementsSorted()
    {
        var result = MergeSort.Sort(new[] { 1, 2 });
        Assert.Equal(new[] { 1, 2 }, result);
    }

    [Fact]
    public void TwoElementsUnsorted()
    {
        var result = MergeSort.Sort(new[] { 2, 1 });
        Assert.Equal(new[] { 1, 2 }, result);
    }

    [Fact]
    public void BasicSort()
    {
        var result = MergeSort.Sort(new[] { 5, 2, 8, 1, 9 });
        Assert.Equal(new[] { 1, 2, 5, 8, 9 }, result);
    }

    [Fact]
    public void AlreadySorted()
    {
        var result = MergeSort.Sort(new[] { 1, 2, 3, 4, 5 });
        Assert.Equal(new[] { 1, 2, 3, 4, 5 }, result);
    }

    [Fact]
    public void ReverseSorted()
    {
        var result = MergeSort.Sort(new[] { 5, 4, 3, 2, 1 });
        Assert.Equal(new[] { 1, 2, 3, 4, 5 }, result);
    }

    [Fact]
    public void WithDuplicates()
    {
        var result = MergeSort.Sort(new[] { 3, 1, 4, 1, 5, 9, 2, 6, 5 });
        Assert.Equal(new[] { 1, 1, 2, 3, 4, 5, 5, 6, 9 }, result);
    }

    [Fact]
    public void AllSameValues()
    {
        var result = MergeSort.Sort(new[] { 7, 7, 7, 7, 7 });
        Assert.Equal(new[] { 7, 7, 7, 7, 7 }, result);
    }

    [Fact]
    public void DoesNotModifyOriginal()
    {
        var original = new[] { 5, 2, 8, 1, 9 };
        var originalCopy = original.ToArray();
        MergeSort.Sort(original);
        Assert.Equal(originalCopy, original);
    }

    [Fact]
    public void StabilityPreservesOrder()
    {
        var arr = new[] { 1, 1, 1, 1 };
        var result = MergeSort.Sort(arr);
        Assert.Equal(arr, result);
    }

    [Fact]
    public void LargerArray()
    {
        var arr = new[] { 10, 7, 8, 9, 1, 5, 3, 2, 6, 4 };
        var result = MergeSort.Sort(arr);
        Assert.Equal(new[] { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 }, result);
    }

    [Fact]
    public void NegativeNumbers()
    {
        var result = MergeSort.Sort(new[] { -5, 2, -8, 0, 9 });
        Assert.Equal(new[] { -8, -5, 0, 2, 9 }, result);
    }
}
