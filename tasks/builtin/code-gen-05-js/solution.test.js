const { ConfigMergeError, mergeConfigs, validateConfig } = require('./config_merge');

describe('mergeConfigs', () => {
    test('simple merge', () => {
        const result = mergeConfigs({ a: 1 }, { b: 2 });
        expect(result).toEqual({ a: 1, b: 2 });
    });

    test('overlay wins', () => {
        const result = mergeConfigs({ a: 1 }, { a: 2 });
        expect(result).toEqual({ a: 2 });
    });

    test('nested merge', () => {
        const result = mergeConfigs({ a: { b: 1 } }, { a: { c: 2 } });
        expect(result).toEqual({ a: { b: 1, c: 2 } });
    });

    test('deep nested merge', () => {
        const result = mergeConfigs(
            { a: { b: { c: 1 } } },
            { a: { b: { d: 2 } } }
        );
        expect(result).toEqual({ a: { b: { c: 1, d: 2 } } });
    });

    test('delete sentinel', () => {
        const result = mergeConfigs({ a: 1, b: 2 }, { a: '__delete__' });
        expect(result).toEqual({ b: 2 });
    });

    test('multiple overlays', () => {
        const result = mergeConfigs({ a: 1 }, { b: 2 }, { c: 3 });
        expect(result).toEqual({ a: 1, b: 2, c: 3 });
    });

    test('multiple overlays precedence', () => {
        const result = mergeConfigs({ a: 1 }, { a: 2 }, { a: 3 });
        expect(result).toEqual({ a: 3 });
    });

    test('arrays replaced not merged', () => {
        const result = mergeConfigs({ a: [1, 2] }, { a: [3, 4] });
        expect(result).toEqual({ a: [3, 4] });
    });

    test('type conflict throws', () => {
        expect(() => mergeConfigs({ a: 1 }, { a: { b: 2 } })).toThrow(ConfigMergeError);
        expect(() => mergeConfigs({ a: { b: 1 } }, { a: 2 })).toThrow(ConfigMergeError);
    });

    test('circular reference throws', () => {
        const circular = { a: 1 };
        circular.self = circular;
        expect(() => mergeConfigs(circular, { b: 2 })).toThrow(ConfigMergeError);
    });

    test('does not mutate inputs', () => {
        const base = { a: 1 };
        const overlay = { b: 2 };
        mergeConfigs(base, overlay);
        expect(base).toEqual({ a: 1 });
        expect(overlay).toEqual({ b: 2 });
    });

    test('nested does not mutate', () => {
        const base = { a: { b: 1 } };
        const overlay = { a: { c: 2 } };
        const result = mergeConfigs(base, overlay);
        expect(base).toEqual({ a: { b: 1 } });
        expect(result).toEqual({ a: { b: 1, c: 2 } });
    });
});

describe('validateConfig', () => {
    test('valid config', () => {
        const violations = validateConfig({ port: 8080 }, { port: Number });
        expect(violations).toEqual([]);
    });

    test('missing key', () => {
        const violations = validateConfig({}, { port: Number });
        expect(violations).toContain("Missing required key: 'port'");
    });

    test('type mismatch', () => {
        const violations = validateConfig({ port: 'string' }, { port: Number });
        expect(violations.length).toBeGreaterThan(0);
        expect(violations[0]).toMatch(/type mismatch/i);
    });

    test('nested validation', () => {
        const config = { server: { port: 8080, host: 'localhost' } };
        const schema = { server: { port: Number, host: String } };
        const violations = validateConfig(config, schema);
        expect(violations).toEqual([]);
    });

    test('nested missing key', () => {
        const config = { server: { port: 8080 } };
        const schema = { server: { port: Number, host: String } };
        const violations = validateConfig(config, schema);
        expect(violations).toContain("Missing required key: 'server.host'");
    });

    test('nested type mismatch', () => {
        const config = { server: { port: 'wrong' } };
        const schema = { server: { port: Number } };
        const violations = validateConfig(config, schema);
        expect(violations.length).toBeGreaterThan(0);
    });

    test('boolean validation', () => {
        const violations = validateConfig({ enabled: true }, { enabled: Boolean });
        expect(violations).toEqual([]);
    });

    test('string validation', () => {
        const violations = validateConfig({ name: 'test' }, { name: String });
        expect(violations).toEqual([]);
    });

    test('multiple violations', () => {
        const config = { port: 'wrong' };
        const schema = { port: Number, host: String };
        const violations = validateConfig(config, schema);
        expect(violations.length).toBe(2);
    });
});
