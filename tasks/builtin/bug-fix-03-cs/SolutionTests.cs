using Xunit;
using System.Threading.Tasks;
using System.Linq;

public class ThreadSafeCounterTests
{
    [Fact]
    public void BasicIncrement()
    {
        var counter = new ThreadSafeCounter();
        counter.Increment();
        Assert.Equal(1, counter.GetValue());
    }

    [Fact]
    public void BasicDecrement()
    {
        var counter = new ThreadSafeCounter();
        counter.Increment();
        counter.Decrement();
        Assert.Equal(0, counter.GetValue());
    }

    [Fact]
    public void Reset()
    {
        var counter = new ThreadSafeCounter();
        counter.Increment();
        counter.Increment();
        counter.Reset();
        Assert.Equal(0, counter.GetValue());
    }

    [Fact]
    public void IncrementBy()
    {
        var counter = new ThreadSafeCounter();
        counter.IncrementBy(5);
        Assert.Equal(5, counter.GetValue());
    }

    [Fact]
    public async Task ConcurrentIncrements()
    {
        var counter = new ThreadSafeCounter();
        int iterations = 1000;
        int threadCount = 10;

        var tasks = Enumerable.Range(0, threadCount)
            .Select(_ => Task.Run(() =>
            {
                for (int i = 0; i < iterations; i++)
                    counter.Increment();
            }))
            .ToArray();

        await Task.WhenAll(tasks);

        Assert.Equal(iterations * threadCount, counter.GetValue());
    }

    [Fact]
    public async Task ConcurrentDecrements()
    {
        var counter = new ThreadSafeCounter();
        int iterations = 1000;
        int threadCount = 10;

        var tasks = Enumerable.Range(0, threadCount)
            .Select(_ => Task.Run(() =>
            {
                for (int i = 0; i < iterations; i++)
                    counter.Decrement();
            }))
            .ToArray();

        await Task.WhenAll(tasks);

        Assert.Equal(-iterations * threadCount, counter.GetValue());
    }

    [Fact]
    public async Task ConcurrentIncrementsAndDecrements()
    {
        var counter = new ThreadSafeCounter();
        int iterations = 1000;

        var incrementTask = Task.Run(() =>
        {
            for (int i = 0; i < iterations; i++)
                counter.Increment();
        });

        var decrementTask = Task.Run(() =>
        {
            for (int i = 0; i < iterations; i++)
                counter.Decrement();
        });

        await Task.WhenAll(incrementTask, decrementTask);

        Assert.Equal(0, counter.GetValue());
    }

    [Fact]
    public async Task ConcurrentIncrementBy()
    {
        var counter = new ThreadSafeCounter();
        int iterations = 100;
        int threadCount = 10;

        var tasks = Enumerable.Range(0, threadCount)
            .Select(_ => Task.Run(() =>
            {
                for (int i = 0; i < iterations; i++)
                    counter.IncrementBy(10);
            }))
            .ToArray();

        await Task.WhenAll(tasks);

        Assert.Equal(10 * iterations * threadCount, counter.GetValue());
    }

    [Fact]
    public async Task ConcurrentReset()
    {
        var counter = new ThreadSafeCounter();

        var tasks = Enumerable.Range(0, 10)
            .Select(i => Task.Run(() =>
            {
                if (i % 2 == 0)
                    counter.Increment();
                else
                    counter.Reset();
            }))
            .ToArray();

        await Task.WhenAll(tasks);

        int value = counter.GetValue();
        Assert.True(value >= 0 && value <= 5);
    }

    [Fact]
    public async Task ConcurrentGetValue()
    {
        var counter = new ThreadSafeCounter();
        counter.IncrementBy(100);

        var tasks = Enumerable.Range(0, 100)
            .Select(_ => Task.Run(() =>
            {
                int val = counter.GetValue();
                Assert.True(val >= 0);
            }))
            .ToArray();

        await Task.WhenAll(tasks);
    }

    [Fact]
    public async Task MixedOperations()
    {
        var counter = new ThreadSafeCounter();
        int iterations = 500;

        var task1 = Task.Run(() =>
        {
            for (int i = 0; i < iterations; i++)
                counter.Increment();
        });

        var task2 = Task.Run(() =>
        {
            for (int i = 0; i < iterations / 2; i++)
                counter.IncrementBy(2);
        });

        var task3 = Task.Run(() =>
        {
            for (int i = 0; i < iterations / 2; i++)
                counter.Decrement();
        });

        await Task.WhenAll(task1, task2, task3);

        Assert.Equal(iterations + iterations - iterations / 2, counter.GetValue());
    }
}
