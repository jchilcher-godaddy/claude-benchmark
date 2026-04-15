using System;

public static class Fibonacci
{
    public static long Calculate(int n)
    {
        if (n < 0)
            throw new ArgumentException("n must be non-negative", nameof(n));

        if (n == 0) return 0;
        if (n == 1) return 1;

        long prev = 0, curr = 1;
        for (int i = 2; i <= n; i++)
        {
            (prev, curr) = (curr, prev + curr);
        }
        return curr;
    }
}
