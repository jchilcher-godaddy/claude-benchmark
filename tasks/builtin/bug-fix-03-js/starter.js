class AsyncCounter {
    constructor() {
        this.value = 0;
    }

    async increment() {
        const current = this.value;
        await new Promise(resolve => setTimeout(resolve, 0));
        this.value = current + 1;
    }

    async decrement() {
        this.value -= 1;
    }

    get() {
        return this.value;
    }

    reset() {
        this.value = 0;
    }

    async incrementBy(n) {
        const current = this.get();
        await new Promise(resolve => setTimeout(resolve, 0));
        this.value = current + n;
    }
}

module.exports = { AsyncCounter };
