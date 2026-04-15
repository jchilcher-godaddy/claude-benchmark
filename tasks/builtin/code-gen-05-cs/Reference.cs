using System;
using System.Collections.Generic;
using System.Linq;

public class ConfigMergeException : Exception
{
    public ConfigMergeException(string message) : base(message) { }
}

public static class ConfigMerger
{
    private const string DeleteSentinel = "__delete__";

    public static Dictionary<string, object?> MergeConfigs(
        Dictionary<string, object?> baseConfig,
        params Dictionary<string, object?>[] overlays)
    {
        var visited = new HashSet<object>();
        var result = DeepCopy(baseConfig, visited);

        foreach (var overlay in overlays)
        {
            visited.Clear();
            result = MergeTwo(result, overlay, visited, new HashSet<object>());
        }

        return result;
    }

    private static Dictionary<string, object?> MergeTwo(
        Dictionary<string, object?> baseDict,
        Dictionary<string, object?> overlay,
        HashSet<object> visited,
        HashSet<object> currentPath)
    {
        if (currentPath.Contains(overlay))
            throw new ConfigMergeException("Circular reference detected");

        var merged = new Dictionary<string, object?>(baseDict);
        currentPath.Add(overlay);

        foreach (var kvp in overlay)
        {
            if (kvp.Value is string str && str == DeleteSentinel)
            {
                merged.Remove(kvp.Key);
                continue;
            }

            if (!merged.ContainsKey(kvp.Key))
            {
                merged[kvp.Key] = DeepCopy(kvp.Value, new HashSet<object>());
                continue;
            }

            var baseValue = merged[kvp.Key];
            var overlayValue = kvp.Value;

            bool baseIsDict = baseValue is Dictionary<string, object?>;
            bool overlayIsDict = overlayValue is Dictionary<string, object?>;

            if (baseIsDict && overlayIsDict)
            {
                merged[kvp.Key] = MergeTwo(
                    (Dictionary<string, object?>)baseValue,
                    (Dictionary<string, object?>)overlayValue,
                    visited,
                    new HashSet<object>(currentPath));
            }
            else if (baseIsDict != overlayIsDict)
            {
                throw new ConfigMergeException(
                    $"Type conflict at key '{kvp.Key}': cannot merge dictionary with scalar");
            }
            else
            {
                merged[kvp.Key] = DeepCopy(overlayValue, new HashSet<object>());
            }
        }

        currentPath.Remove(overlay);
        return merged;
    }

    private static object? DeepCopy(object? value, HashSet<object> visited)
    {
        if (value == null) return null;

        if (value is string || value is int || value is long ||
            value is double || value is bool || value is float)
            return value;

        if (value is Dictionary<string, object?> dict)
        {
            if (visited.Contains(dict))
                throw new ConfigMergeException("Circular reference detected");

            visited.Add(dict);
            var copy = new Dictionary<string, object?>();
            foreach (var kvp in dict)
            {
                copy[kvp.Key] = DeepCopy(kvp.Value, visited);
            }
            return copy;
        }

        return value;
    }

    public static List<string> ValidateConfig(
        Dictionary<string, object?> merged,
        Dictionary<string, Type> schema)
    {
        var errors = new List<string>();
        ValidateRecursive(merged, schema, "", errors);
        return errors;
    }

    private static void ValidateRecursive(
        Dictionary<string, object?> config,
        Dictionary<string, Type> schema,
        string path,
        List<string> errors)
    {
        foreach (var kvp in schema)
        {
            var fullPath = string.IsNullOrEmpty(path) ? kvp.Key : $"{path}.{kvp.Key}";

            if (!config.ContainsKey(kvp.Key))
            {
                errors.Add($"Missing required key: {fullPath}");
                continue;
            }

            var value = config[kvp.Key];
            var expectedType = kvp.Value;

            if (expectedType == typeof(Dictionary<string, Type>))
            {
                if (value is Dictionary<string, object?> nestedConfig)
                {
                    continue;
                }
                else
                {
                    errors.Add($"Type mismatch at {fullPath}: expected nested config, got {value?.GetType().Name ?? "null"}");
                }
            }
            else if (value == null)
            {
                if (!expectedType.IsClass && expectedType != typeof(string))
                {
                    errors.Add($"Type mismatch at {fullPath}: expected {expectedType.Name}, got null");
                }
            }
            else if (value is Dictionary<string, object?> nestedDict && expectedType == typeof(Dictionary<string, object?>))
            {
                continue;
            }
            else
            {
                var actualType = value.GetType();
                if (expectedType == typeof(int) && actualType == typeof(long))
                {
                    var longVal = (long)value;
                    if (longVal >= int.MinValue && longVal <= int.MaxValue)
                        continue;
                }

                if (actualType != expectedType && !(expectedType.IsAssignableFrom(actualType)))
                {
                    errors.Add($"Type mismatch at {fullPath}: expected {expectedType.Name}, got {actualType.Name}");
                }
            }
        }
    }
}
