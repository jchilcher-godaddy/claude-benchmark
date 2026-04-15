function fibonacci(n) {
    if (n < 0) {
        throw new Error("n must be non-negative");
    }
    if (n === 0) return 0;
    if (n === 1) return 1;

    let prev = 0, curr = 1;
    for (let i = 2; i <= n; i++) {
        [prev, curr] = [curr, prev + curr];
    }
    return curr;
}

module.exports = { fibonacci };
