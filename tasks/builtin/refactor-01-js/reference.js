function sumAmountsByField(records, field, value) {
    let total = 0;
    for (const record of records) {
        if (record[field] === value && record.amount !== undefined) {
            const amount = record.amount;
            if (amount > 0) {
                total += amount;
            }
        }
    }
    return total;
}

function countRecordsByFields(records, filters) {
    let count = 0;
    for (const record of records) {
        const matches = Object.entries(filters).every(
            ([field, value]) => record[field] === value
        );
        if (matches) {
            count++;
        }
    }
    return count;
}

function processRecords(records) {
    return {
        activeTotal: sumAmountsByField(records, 'status', 'active'),
        highPriorityTotal: sumAmountsByField(records, 'priority', 'high'),
        pendingTotal: sumAmountsByField(records, 'status', 'pending'),
        activeHighPriorityCount: countRecordsByFields(records, {
            status: 'active',
            priority: 'high'
        }),
        pendingHighPriorityCount: countRecordsByFields(records, {
            status: 'pending',
            priority: 'high'
        })
    };
}

module.exports = { processRecords };
