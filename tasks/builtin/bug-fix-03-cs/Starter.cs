using System.Threading;

public class ThreadSafeCounter
{
    private int _value = 0;
    private readonly object _lock = new object();

    public void Increment()
    {
        int current = _value;
        Thread.Sleep(1);
        _value = current + 1;
    }

    public void Decrement()
    {
        lock (_lock)
        {
            _value--;
        }
    }

    public int GetValue()
    {
        return _value;
    }

    public void Reset()
    {
        lock (_lock)
        {
            _value = 0;
        }
    }

    public void IncrementBy(int n)
    {
        int current = GetValue();
        lock (_lock)
        {
            _value = current + n;
        }
    }
}
