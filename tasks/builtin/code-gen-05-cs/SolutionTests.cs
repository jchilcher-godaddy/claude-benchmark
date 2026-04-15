using Xunit;
using System;
using System.Collections.Generic;
using System.Linq;

public class ConfigMergerTests
{
    [Fact]
    public void MergeSimpleOverride()
    {
        var baseConfig = new Dictionary<string, object?>
        {
            ["a"] = 1,
            ["b"] = 2
        };
        var overlay = new Dictionary<string, object?>
        {
            ["b"] = 3
        };

        var result = ConfigMerger.MergeConfigs(baseConfig, overlay);

        Assert.Equal(1, result["a"]);
        Assert.Equal(3, result["b"]);
    }

    [Fact]
    public void MergeNestedDictionaries()
    {
        var baseConfig = new Dictionary<string, object?>
        {
            ["outer"] = new Dictionary<string, object?>
            {
                ["inner"] = 1
            }
        };
        var overlay = new Dictionary<string, object?>
        {
            ["outer"] = new Dictionary<string, object?>
            {
                ["inner"] = 2
            }
        };

        var result = ConfigMerger.MergeConfigs(baseConfig, overlay);
        var outer = (Dictionary<string, object?>)result["outer"]!;

        Assert.Equal(2, outer["inner"]);
    }

    [Fact]
    public void DeleteSentinel()
    {
        var baseConfig = new Dictionary<string, object?>
        {
            ["a"] = 1,
            ["b"] = 2
        };
        var overlay = new Dictionary<string, object?>
        {
            ["b"] = "__delete__"
        };

        var result = ConfigMerger.MergeConfigs(baseConfig, overlay);

        Assert.True(result.ContainsKey("a"));
        Assert.False(result.ContainsKey("b"));
    }

    [Fact]
    public void TypeConflictThrows()
    {
        var baseConfig = new Dictionary<string, object?>
        {
            ["a"] = new Dictionary<string, object?> { ["x"] = 1 }
        };
        var overlay = new Dictionary<string, object?>
        {
            ["a"] = 42
        };

        Assert.Throws<ConfigMergeException>(() =>
            ConfigMerger.MergeConfigs(baseConfig, overlay));
    }

    [Fact]
    public void DoesNotMutateInputs()
    {
        var baseConfig = new Dictionary<string, object?> { ["a"] = 1 };
        var overlay = new Dictionary<string, object?> { ["a"] = 2 };

        ConfigMerger.MergeConfigs(baseConfig, overlay);

        Assert.Equal(1, baseConfig["a"]);
        Assert.Equal(2, overlay["a"]);
    }

    [Fact]
    public void MultipleOverlays()
    {
        var baseConfig = new Dictionary<string, object?> { ["a"] = 1 };
        var overlay1 = new Dictionary<string, object?> { ["a"] = 2 };
        var overlay2 = new Dictionary<string, object?> { ["a"] = 3 };

        var result = ConfigMerger.MergeConfigs(baseConfig, overlay1, overlay2);

        Assert.Equal(3, result["a"]);
    }

    [Fact]
    public void ValidateConfigSuccess()
    {
        var config = new Dictionary<string, object?>
        {
            ["port"] = 8080,
            ["host"] = "localhost"
        };
        var schema = new Dictionary<string, Type>
        {
            ["port"] = typeof(int),
            ["host"] = typeof(string)
        };

        var errors = ConfigMerger.ValidateConfig(config, schema);

        Assert.Empty(errors);
    }

    [Fact]
    public void ValidateMissingKey()
    {
        var config = new Dictionary<string, object?> { ["port"] = 8080 };
        var schema = new Dictionary<string, Type>
        {
            ["port"] = typeof(int),
            ["host"] = typeof(string)
        };

        var errors = ConfigMerger.ValidateConfig(config, schema);

        Assert.Single(errors);
        Assert.Contains("host", errors[0]);
    }

    [Fact]
    public void ValidateTypeMismatch()
    {
        var config = new Dictionary<string, object?>
        {
            ["port"] = "not-an-int"
        };
        var schema = new Dictionary<string, Type>
        {
            ["port"] = typeof(int)
        };

        var errors = ConfigMerger.ValidateConfig(config, schema);

        Assert.Single(errors);
        Assert.Contains("port", errors[0]);
        Assert.Contains("mismatch", errors[0].ToLower());
    }

    [Fact]
    public void CircularReferenceThrows()
    {
        var circular = new Dictionary<string, object?>();
        circular["self"] = circular;

        var baseConfig = new Dictionary<string, object?> { ["a"] = 1 };

        Assert.Throws<ConfigMergeException>(() =>
            ConfigMerger.MergeConfigs(baseConfig, circular));
    }

    [Fact]
    public void MergeAddNewKeys()
    {
        var baseConfig = new Dictionary<string, object?> { ["a"] = 1 };
        var overlay = new Dictionary<string, object?> { ["b"] = 2 };

        var result = ConfigMerger.MergeConfigs(baseConfig, overlay);

        Assert.Equal(1, result["a"]);
        Assert.Equal(2, result["b"]);
    }

    [Fact]
    public void MergeDeepNesting()
    {
        var baseConfig = new Dictionary<string, object?>
        {
            ["level1"] = new Dictionary<string, object?>
            {
                ["level2"] = new Dictionary<string, object?>
                {
                    ["value"] = 1
                }
            }
        };
        var overlay = new Dictionary<string, object?>
        {
            ["level1"] = new Dictionary<string, object?>
            {
                ["level2"] = new Dictionary<string, object?>
                {
                    ["value"] = 2
                }
            }
        };

        var result = ConfigMerger.MergeConfigs(baseConfig, overlay);
        var level1 = (Dictionary<string, object?>)result["level1"]!;
        var level2 = (Dictionary<string, object?>)level1["level2"]!;

        Assert.Equal(2, level2["value"]);
    }
}
