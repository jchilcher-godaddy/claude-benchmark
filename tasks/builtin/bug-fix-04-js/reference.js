class QueryBuilder {
    constructor(table, allowedColumns = null) {
        this.allowedColumns = allowedColumns;
        this._validateName(table, 'table');
        this.table = table;
        this._columns = ['*'];
        this._whereConditions = [];
        this._whereParams = [];
        this._orderBy = null;
    }

    _validateName(name, kind = 'column') {
        const validPattern = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
        if (!validPattern.test(name)) {
            throw new Error(`Invalid ${kind} name: ${name}`);
        }
        if (this.allowedColumns && kind === 'column' && name !== '*') {
            if (!this.allowedColumns.includes(name)) {
                throw new Error(`Column '${name}' not in allowed columns: ${this.allowedColumns.join(', ')}`);
            }
        }
    }

    select(...columns) {
        for (const col of columns) {
            this._validateName(col, 'column');
        }
        this._columns = columns.length > 0 ? columns : ['*'];
        return this;
    }

    where(condition, value = null) {
        if (value !== null) {
            this._validateName(condition, 'column');
            this._whereConditions.push(`${condition} = ?`);
            this._whereParams.push(value);
        } else {
            this._whereConditions.push(condition);
        }
        return this;
    }

    orderBy(column, direction = 'ASC') {
        this._validateName(column, 'column');
        const dir = direction.toUpperCase();
        if (dir !== 'ASC' && dir !== 'DESC') {
            throw new Error(`Invalid direction: ${direction}`);
        }
        this._orderBy = { column, direction: dir };
        return this;
    }

    build() {
        const cols = this._columns.join(', ');
        let sql = `SELECT ${cols} FROM ${this.table}`;

        const params = [...this._whereParams];
        if (this._whereConditions.length > 0) {
            sql += ' WHERE ' + this._whereConditions.join(' AND ');
        }

        if (this._orderBy) {
            sql += ` ORDER BY ${this._orderBy.column} ${this._orderBy.direction}`;
        }

        return { sql, params };
    }
}

module.exports = { QueryBuilder };
