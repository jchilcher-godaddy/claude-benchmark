const { QueryBuilder } = require('./solution');

test('simple select', () => {
    const qb = new QueryBuilder('users');
    const { sql, params } = qb.build();
    expect(sql).toBe('SELECT * FROM users');
    expect(params).toEqual([]);
});

test('select specific columns', () => {
    const qb = new QueryBuilder('users');
    const { sql } = qb.select('id', 'name').build();
    expect(sql).toBe('SELECT id, name FROM users');
});

test('where with parameterized value', () => {
    const qb = new QueryBuilder('users');
    const { sql, params } = qb.where('status', 'active').build();
    expect(sql).toBe('SELECT * FROM users WHERE status = ?');
    expect(params).toEqual(['active']);
});

test('multiple where clauses chain with AND', () => {
    const qb = new QueryBuilder('users');
    const { sql, params } = qb
        .where('status', 'active')
        .where('age', 25)
        .build();
    expect(sql).toBe('SELECT * FROM users WHERE status = ? AND age = ?');
    expect(params).toEqual(['active', 25]);
});

test('order by', () => {
    const qb = new QueryBuilder('users');
    const { sql } = qb.orderBy('created_at', 'DESC').build();
    expect(sql).toBe('SELECT * FROM users ORDER BY created_at DESC');
});

test('combined query', () => {
    const qb = new QueryBuilder('users');
    const { sql, params } = qb
        .select('id', 'name')
        .where('status', 'active')
        .orderBy('name', 'ASC')
        .build();
    expect(sql).toBe('SELECT id, name FROM users WHERE status = ? ORDER BY name ASC');
    expect(params).toEqual(['active']);
});

test('rejects SQL injection in table name', () => {
    expect(() => new QueryBuilder('users; DROP TABLE users--')).toThrow();
});

test('rejects SQL injection in column name', () => {
    const qb = new QueryBuilder('users');
    expect(() => qb.select('id', 'name; DROP TABLE users--')).toThrow();
});

test('rejects SQL injection in where column', () => {
    const qb = new QueryBuilder('users');
    expect(() => qb.where('status; DROP TABLE users--', 'active')).toThrow();
});

test('rejects SQL injection in order by', () => {
    const qb = new QueryBuilder('users');
    expect(() => qb.orderBy('id; DROP TABLE users--')).toThrow();
});

test('validates against whitelist', () => {
    const qb = new QueryBuilder('users', ['id', 'name', 'email']);
    expect(() => qb.select('password')).toThrow();
});

test('allows whitelisted columns', () => {
    const qb = new QueryBuilder('users', ['id', 'name', 'email']);
    const { sql } = qb.select('id', 'name').build();
    expect(sql).toBe('SELECT id, name FROM users');
});

test('where value not escaped in SQL string', () => {
    const qb = new QueryBuilder('users');
    const { sql, params } = qb.where('name', "'; DROP TABLE users--").build();
    expect(sql).not.toContain('DROP TABLE');
    expect(sql).toBe('SELECT * FROM users WHERE name = ?');
    expect(params).toEqual(["'; DROP TABLE users--"]);
});

test('invalid direction in order by', () => {
    const qb = new QueryBuilder('users');
    expect(() => qb.orderBy('id', 'INVALID')).toThrow();
});

test('case insensitive direction', () => {
    const qb = new QueryBuilder('users');
    const { sql } = qb.orderBy('id', 'asc').build();
    expect(sql).toBe('SELECT * FROM users ORDER BY id ASC');
});
