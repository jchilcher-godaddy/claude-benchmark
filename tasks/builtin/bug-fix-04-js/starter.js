class QueryBuilder {
    constructor(table, allowedColumns = null) {
        this.table = table;
        this.allowedColumns = allowedColumns;
        this._columns = ['*'];
        this._whereClause = null;
        this._whereParams = [];
        this._orderBy = null;
    }

    select(...columns) {
        this._columns = columns.length > 0 ? columns : ['*'];
        return this;
    }

    where(condition, value = null) {
        if (value !== null) {
            this._whereClause = `${condition} = '${value}'`;
            this._whereParams = [];
        } else {
            this._whereClause = condition;
        }
        return this;
    }

    orderBy(column, direction = 'ASC') {
        this._orderBy = `${column} ${direction}`;
        return this;
    }

    build() {
        const cols = this._columns.join(', ');
        let sql = `SELECT ${cols} FROM ${this.table}`;

        const params = [];
        if (this._whereClause) {
            sql += ` WHERE ${this._whereClause}`;
            params.push(...this._whereParams);
        }

        if (this._orderBy) {
            sql += ` ORDER BY ${this._orderBy}`;
        }

        return { sql, params };
    }
}

module.exports = { QueryBuilder };
