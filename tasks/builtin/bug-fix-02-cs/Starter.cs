using System.Linq;

public static class MergeSort
{
    public static int[] Sort(int[] arr)
    {
        if (arr.Length <= 1)
            return arr.ToArray();

        int mid = arr.Length / 2;
        var left = Sort(arr.Take(mid).ToArray());
        var right = Sort(arr.Skip(mid).ToArray());

        return Merge(left, right);
    }

    private static int[] Merge(int[] left, int[] right)
    {
        var result = new int[left.Length + right.Length];
        int i = 0, j = 0, k = 0;

        while (i < left.Length && j < right.Length)
        {
            if (left[i] > right[j])
            {
                result[k++] = left[i++];
            }
            else
            {
                result[k++] = right[j++];
            }
        }

        while (i < left.Length)
            result[k++] = left[j++];

        while (j < right.Length)
            result[k++] = right[j++];

        return result;
    }
}
