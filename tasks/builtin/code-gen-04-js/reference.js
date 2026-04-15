const crypto = require('crypto');

class URLShortener {
    constructor() {
        this.urlToCode = new Map();
        this.codeToEntry = new Map();
        this.DANGEROUS_SCHEMES = new Set(['javascript', 'data', 'vbscript']);
    }

    _validateUrl(url) {
        if (!url || typeof url !== 'string') {
            throw new Error('URL must be a non-empty string');
        }
        let parsed;
        try {
            parsed = new URL(url);
        } catch (e) {
            throw new Error(`Invalid URL: ${url}`);
        }
        if (!parsed.protocol || !parsed.hostname) {
            throw new Error(`Invalid URL: missing scheme or host: ${url}`);
        }
        const scheme = parsed.protocol.replace(':', '').toLowerCase();
        if (this.DANGEROUS_SCHEMES.has(scheme)) {
            throw new Error(`Dangerous URL scheme: ${scheme}`);
        }
    }

    _generateCode(url, attempt = 0) {
        const data = `${url}:${attempt}`;
        return crypto.createHash('sha256').update(data).digest('hex').substring(0, 8);
    }

    shorten(url) {
        this._validateUrl(url);
        if (this.urlToCode.has(url)) {
            return this.urlToCode.get(url);
        }

        let attempt = 0;
        let code = this._generateCode(url, attempt);
        while (this.codeToEntry.has(code)) {
            attempt++;
            code = this._generateCode(url, attempt);
        }

        this.codeToEntry.set(code, {
            originalUrl: url,
            clickCount: 0,
            createdAt: new Date()
        });
        this.urlToCode.set(url, code);
        return code;
    }

    resolve(shortCode) {
        if (!this.codeToEntry.has(shortCode)) {
            throw new Error(`Short code not found: ${shortCode}`);
        }
        const entry = this.codeToEntry.get(shortCode);
        entry.clickCount++;
        return entry.originalUrl;
    }

    getStats(shortCode) {
        if (!this.codeToEntry.has(shortCode)) {
            throw new Error(`Short code not found: ${shortCode}`);
        }
        const entry = this.codeToEntry.get(shortCode);
        return {
            originalUrl: entry.originalUrl,
            clickCount: entry.clickCount,
            createdAt: entry.createdAt
        };
    }

    delete(shortCode) {
        if (!this.codeToEntry.has(shortCode)) {
            return false;
        }
        const entry = this.codeToEntry.get(shortCode);
        const url = entry.originalUrl;
        this.codeToEntry.delete(shortCode);
        this.urlToCode.delete(url);
        return true;
    }
}

module.exports = { URLShortener };
