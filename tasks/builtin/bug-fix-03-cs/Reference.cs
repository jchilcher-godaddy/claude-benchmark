public class ThreadSafeCounter
{
    private int _value = 0;
    private readonly object _lock = new object();

    public void Increment()
    {
        lock (_lock)
        {
            _value++;
        }
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
        lock (_lock)
        {
            return _value;
        }
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
        lock (_lock)
        {
            _value += n;
        }
    }
}
