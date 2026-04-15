function processRecords(records) {
    let activeTotal = 0;
    for (const record of records) {
        if (record.status === 'active' && record.amount !== undefined) {
            const amount = record.amount;
            if (amount > 0) {
                activeTotal += amount;
            }
        }
    }

    let highPriorityTotal = 0;
    for (const record of records) {
        if (record.priority === 'high' && record.amount !== undefined) {
            const amount = record.amount;
            if (amount > 0) {
                highPriorityTotal += amount;
            }
        }
    }

    let pendingTotal = 0;
    for (const record of records) {
        if (record.status === 'pending' && record.amount !== undefined) {
            const amount = record.amount;
            if (amount > 0) {
                pendingTotal += amount;
            }
        }
    }

    let activeHighPriorityCount = 0;
    for (const record of records) {
        if (record.status === 'active' && record.priority === 'high') {
            activeHighPriorityCount++;
        }
    }

    let pendingHighPriorityCount = 0;
    for (const record of records) {
        if (record.status === 'pending' && record.priority === 'high') {
            pendingHighPriorityCount++;
        }
    }

    return {
        activeTotal,
        highPriorityTotal,
        pendingTotal,
        activeHighPriorityCount,
        pendingHighPriorityCount
    };
}

module.exports = { processRecords };
