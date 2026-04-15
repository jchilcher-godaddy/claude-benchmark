class AsyncCounter {
    constructor() {
        this.value = 0;
        this.queue = Promise.resolve();
    }

    async increment() {
        this.queue = this.queue.then(async () => {
            const current = this.value;
            await new Promise(resolve => setTimeout(resolve, 0));
            this.value = current + 1;
        });
        await this.queue;
    }

    async decrement() {
        this.queue = this.queue.then(() => {
            this.value -= 1;
        });
        await this.queue;
    }

    get() {
        return this.value;
    }

    reset() {
        this.queue = this.queue.then(() => {
            this.value = 0;
        });
    }

    async incrementBy(n) {
        this.queue = this.queue.then(async () => {
            const current = this.value;
            await new Promise(resolve => setTimeout(resolve, 0));
            this.value = current + n;
        });
        await this.queue;
    }
}

module.exports = { AsyncCounter };
