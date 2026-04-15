const { URLShortener } = require('./url_shortener');

test('shorten valid URL', () => {
    const shortener = new URLShortener();
    const code = shortener.shorten('https://example.com');
    expect(code).toBeTruthy();
    expect(code.length).toBeGreaterThanOrEqual(6);
});

test('resolve returns original URL', () => {
    const shortener = new URLShortener();
    const url = 'https://example.com';
    const code = shortener.shorten(url);
    expect(shortener.resolve(code)).toBe(url);
});

test('shorten same URL twice returns same code', () => {
    const shortener = new URLShortener();
    const url = 'https://example.com';
    const code1 = shortener.shorten(url);
    const code2 = shortener.shorten(url);
    expect(code1).toBe(code2);
});

test('rejects invalid URL', () => {
    const shortener = new URLShortener();
    expect(() => shortener.shorten('not-a-url')).toThrow();
    expect(() => shortener.shorten('')).toThrow();
});

test('rejects dangerous schemes', () => {
    const shortener = new URLShortener();
    expect(() => shortener.shorten('javascript:alert(1)')).toThrow(/dangerous/i);
    expect(() => shortener.shorten('data:text/html,<script>alert(1)</script>')).toThrow(/dangerous/i);
    expect(() => shortener.shorten('vbscript:msgbox')).toThrow(/dangerous/i);
});

test('resolve increments click count', () => {
    const shortener = new URLShortener();
    const code = shortener.shorten('https://example.com');
    shortener.resolve(code);
    shortener.resolve(code);
    const stats = shortener.getStats(code);
    expect(stats.clickCount).toBe(2);
});

test('getStats returns correct structure', () => {
    const shortener = new URLShortener();
    const url = 'https://example.com';
    const code = shortener.shorten(url);
    const stats = shortener.getStats(code);
    expect(stats.originalUrl).toBe(url);
    expect(stats.clickCount).toBe(0);
    expect(stats.createdAt).toBeInstanceOf(Date);
});

test('resolve throws on missing code', () => {
    const shortener = new URLShortener();
    expect(() => shortener.resolve('missing')).toThrow();
});

test('getStats throws on missing code', () => {
    const shortener = new URLShortener();
    expect(() => shortener.getStats('missing')).toThrow();
});

test('delete removes mapping', () => {
    const shortener = new URLShortener();
    const code = shortener.shorten('https://example.com');
    expect(shortener.delete(code)).toBe(true);
    expect(() => shortener.resolve(code)).toThrow();
});

test('delete returns false for missing code', () => {
    const shortener = new URLShortener();
    expect(shortener.delete('missing')).toBe(false);
});

test('delete allows re-shortening URL', () => {
    const shortener = new URLShortener();
    const url = 'https://example.com';
    const code1 = shortener.shorten(url);
    shortener.delete(code1);
    const code2 = shortener.shorten(url);
    expect(code2).toBeTruthy();
});

test('handles multiple URLs', () => {
    const shortener = new URLShortener();
    const code1 = shortener.shorten('https://example.com');
    const code2 = shortener.shorten('https://another.com');
    expect(code1).not.toBe(code2);
    expect(shortener.resolve(code1)).toBe('https://example.com');
    expect(shortener.resolve(code2)).toBe('https://another.com');
});

test('URL with path and query', () => {
    const shortener = new URLShortener();
    const url = 'https://example.com/path?query=value#hash';
    const code = shortener.shorten(url);
    expect(shortener.resolve(code)).toBe(url);
});

test('http and https are different URLs', () => {
    const shortener = new URLShortener();
    const code1 = shortener.shorten('http://example.com');
    const code2 = shortener.shorten('https://example.com');
    expect(code1).not.toBe(code2);
});
