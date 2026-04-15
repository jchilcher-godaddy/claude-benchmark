class ConfigMergeError extends Error {
    constructor(message) {
        super(message);
        this.name = 'ConfigMergeError';
    }
}

function mergeConfigs(base, ...overlays) {
    function checkCircular(obj, seen = new Set()) {
        if (seen.has(obj)) {
            throw new ConfigMergeError('Circular reference detected');
        }
        seen.add(obj);
        for (const val of Object.values(obj)) {
            if (val && typeof val === 'object' && !Array.isArray(val)) {
                checkCircular(val, seen);
            }
        }
    }

    function merge(a, b, path = '') {
        const result = { ...a };
        for (const [key, bVal] of Object.entries(b)) {
            const currentPath = path ? `${path}.${key}` : key;

            if (bVal === '__delete__') {
                delete result[key];
                continue;
            }

            if (key in result) {
                const aVal = result[key];
                const aIsObj = aVal && typeof aVal === 'object' && !Array.isArray(aVal);
                const bIsObj = bVal && typeof bVal === 'object' && !Array.isArray(bVal);

                if (aIsObj && bIsObj) {
                    result[key] = merge(aVal, bVal, currentPath);
                } else if (aIsObj !== bIsObj) {
                    const aType = aIsObj ? 'object' : typeof aVal;
                    const bType = bIsObj ? 'object' : typeof bVal;
                    throw new ConfigMergeError(
                        `Type conflict at '${currentPath}': cannot merge ${aType} with ${bType}`
                    );
                } else {
                    result[key] = bVal;
                }
            } else {
                result[key] = bVal;
            }
        }
        return result;
    }

    checkCircular(base);
    for (const overlay of overlays) {
        checkCircular(overlay);
    }

    let result = { ...base };
    for (const overlay of overlays) {
        result = merge(result, overlay);
    }
    return result;
}

function validateConfig(merged, schema, path = '') {
    const violations = [];

    for (const [key, expected] of Object.entries(schema)) {
        const currentPath = path ? `${path}.${key}` : key;

        if (!(key in merged)) {
            violations.push(`Missing required key: '${currentPath}'`);
            continue;
        }

        const actual = merged[key];
        if (typeof expected === 'object' && !Array.isArray(expected) && expected !== null) {
            if (typeof actual !== 'object' || Array.isArray(actual) || actual === null) {
                const actualType = actual === null ? 'null' : Array.isArray(actual) ? 'array' : typeof actual;
                violations.push(`Type mismatch at '${currentPath}': expected object, got ${actualType}`);
            } else {
                violations.push(...validateConfig(actual, expected, currentPath));
            }
        } else {
            const expectedName = expected === Number ? 'number' :
                                expected === String ? 'string' :
                                expected === Boolean ? 'boolean' : expected.name;
            const actualType = typeof actual;

            if (expected === Number && actualType !== 'number') {
                violations.push(`Type mismatch at '${currentPath}': expected number, got ${actualType}`);
            } else if (expected === String && actualType !== 'string') {
                violations.push(`Type mismatch at '${currentPath}': expected string, got ${actualType}`);
            } else if (expected === Boolean && actualType !== 'boolean') {
                violations.push(`Type mismatch at '${currentPath}': expected boolean, got ${actualType}`);
            }
        }
    }

    return violations;
}

module.exports = { ConfigMergeError, mergeConfigs, validateConfig };
