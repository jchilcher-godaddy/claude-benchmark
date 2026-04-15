package solution

import "sync"

type ThreadSafeCounter struct {
	value int
	mu    sync.Mutex
}

func NewThreadSafeCounter() *ThreadSafeCounter {
	return &ThreadSafeCounter{value: 0}
}

func (c *ThreadSafeCounter) Increment() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value++
}

func (c *ThreadSafeCounter) Decrement() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value--
}

func (c *ThreadSafeCounter) Get() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.value
}

func (c *ThreadSafeCounter) Reset() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value = 0
}

func (c *ThreadSafeCounter) IncrementBy(n int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value += n
}
