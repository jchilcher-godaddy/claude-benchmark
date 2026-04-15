using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

public class UrlStats
{
    public string OriginalUrl { get; set; } = "";
    public int ClickCount { get; set; }
    public DateTime CreatedAt { get; set; }
}

public class UrlShortener
{
    private readonly Dictionary<string, (string Url, UrlStats Stats)> _shortToUrl = new();
    private readonly Dictionary<string, string> _urlToShort = new();

    public string Shorten(string url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri))
            throw new ArgumentException("Invalid URL format", nameof(url));

        var scheme = uri.Scheme.ToLower();
        if (scheme == "javascript" || scheme == "data" || scheme == "vbscript")
            throw new ArgumentException("Dangerous URL scheme not allowed", nameof(url));

        if (string.IsNullOrEmpty(uri.Host))
            throw new ArgumentException("URL must have a host", nameof(url));

        if (_urlToShort.TryGetValue(url, out var existingCode))
            return existingCode;

        string shortCode;
        int attempt = 0;
        do
        {
            shortCode = GenerateShortCode(url, attempt);
            attempt++;
        } while (_shortToUrl.ContainsKey(shortCode));

        var stats = new UrlStats
        {
            OriginalUrl = url,
            ClickCount = 0,
            CreatedAt = DateTime.UtcNow
        };

        _shortToUrl[shortCode] = (url, stats);
        _urlToShort[url] = shortCode;

        return shortCode;
    }

    public string Resolve(string shortCode)
    {
        if (!_shortToUrl.TryGetValue(shortCode, out var entry))
            throw new KeyNotFoundException($"Short code '{shortCode}' not found");

        entry.Stats.ClickCount++;
        return entry.Url;
    }

    public UrlStats GetStats(string shortCode)
    {
        if (!_shortToUrl.TryGetValue(shortCode, out var entry))
            throw new KeyNotFoundException($"Short code '{shortCode}' not found");

        return entry.Stats;
    }

    public bool Delete(string shortCode)
    {
        if (!_shortToUrl.TryGetValue(shortCode, out var entry))
            return false;

        _shortToUrl.Remove(shortCode);
        _urlToShort.Remove(entry.Url);
        return true;
    }

    private string GenerateShortCode(string url, int attempt)
    {
        var input = url + attempt;
        var hashBytes = MD5.HashData(Encoding.UTF8.GetBytes(input));
        var hash = Convert.ToBase64String(hashBytes)
            .Replace("+", "")
            .Replace("/", "")
            .Replace("=", "");
        return hash.Substring(0, Math.Min(8, hash.Length));
    }
}
