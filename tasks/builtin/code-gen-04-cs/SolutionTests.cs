using Xunit;
using System;

public class UrlShortenerTests
{
    [Fact]
    public void ShortenValidUrl()
    {
        var shortener = new UrlShortener();
        var code = shortener.Shorten("https://example.com");
        Assert.NotNull(code);
        Assert.True(code.Length >= 6);
    }

    [Fact]
    public void ResolveShortCode()
    {
        var shortener = new UrlShortener();
        var url = "https://example.com";
        var code = shortener.Shorten(url);
        Assert.Equal(url, shortener.Resolve(code));
    }

    [Fact]
    public void InvalidUrlThrows()
    {
        var shortener = new UrlShortener();
        Assert.Throws<ArgumentException>(() => shortener.Shorten("not-a-url"));
        Assert.Throws<ArgumentException>(() => shortener.Shorten(""));
    }

    [Fact]
    public void DangerousSchemeThrows()
    {
        var shortener = new UrlShortener();
        Assert.Throws<ArgumentException>(() => shortener.Shorten("javascript:alert(1)"));
        Assert.Throws<ArgumentException>(() => shortener.Shorten("data:text/html,<script>alert(1)</script>"));
        Assert.Throws<ArgumentException>(() => shortener.Shorten("vbscript:msgbox(1)"));
    }

    [Fact]
    public void ResolveNonExistentThrows()
    {
        var shortener = new UrlShortener();
        Assert.Throws<KeyNotFoundException>(() => shortener.Resolve("missing"));
    }

    [Fact]
    public void ClickCountIncrementsOnResolve()
    {
        var shortener = new UrlShortener();
        var url = "https://example.com";
        var code = shortener.Shorten(url);

        Assert.Equal(0, shortener.GetStats(code).ClickCount);

        shortener.Resolve(code);
        Assert.Equal(1, shortener.GetStats(code).ClickCount);

        shortener.Resolve(code);
        Assert.Equal(2, shortener.GetStats(code).ClickCount);
    }

    [Fact]
    public void GetStatsReturnsCorrectData()
    {
        var shortener = new UrlShortener();
        var url = "https://example.com/test";
        var code = shortener.Shorten(url);

        var stats = shortener.GetStats(code);
        Assert.Equal(url, stats.OriginalUrl);
        Assert.Equal(0, stats.ClickCount);
        Assert.True(DateTime.UtcNow - stats.CreatedAt < TimeSpan.FromSeconds(1));
    }

    [Fact]
    public void GetStatsNonExistentThrows()
    {
        var shortener = new UrlShortener();
        Assert.Throws<KeyNotFoundException>(() => shortener.GetStats("missing"));
    }

    [Fact]
    public void DeleteRemovesShortCode()
    {
        var shortener = new UrlShortener();
        var url = "https://example.com";
        var code = shortener.Shorten(url);

        Assert.True(shortener.Delete(code));
        Assert.Throws<KeyNotFoundException>(() => shortener.Resolve(code));
    }

    [Fact]
    public void DeleteNonExistentReturnsFalse()
    {
        var shortener = new UrlShortener();
        Assert.False(shortener.Delete("missing"));
    }

    [Fact]
    public void SameUrlReturnsSameCode()
    {
        var shortener = new UrlShortener();
        var url = "https://example.com";
        var code1 = shortener.Shorten(url);
        var code2 = shortener.Shorten(url);

        Assert.Equal(code1, code2);
    }

    [Fact]
    public void DifferentUrlsGetDifferentCodes()
    {
        var shortener = new UrlShortener();
        var code1 = shortener.Shorten("https://example.com");
        var code2 = shortener.Shorten("https://different.com");

        Assert.NotEqual(code1, code2);
    }

    [Fact]
    public void MultipleUrls()
    {
        var shortener = new UrlShortener();
        var urls = new[]
        {
            "https://example.com",
            "https://test.com",
            "https://demo.org"
        };

        foreach (var url in urls)
        {
            var code = shortener.Shorten(url);
            Assert.Equal(url, shortener.Resolve(code));
        }
    }

    [Fact]
    public void DeleteAndReshortenSameUrl()
    {
        var shortener = new UrlShortener();
        var url = "https://example.com";
        var code1 = shortener.Shorten(url);
        shortener.Delete(code1);

        var code2 = shortener.Shorten(url);
        Assert.Equal(url, shortener.Resolve(code2));
    }
}
