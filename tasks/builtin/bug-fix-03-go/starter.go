package solution

import (
	"sync"
	"time"
)

type ThreadSafeCounter struct {
	value int
	mu    sync.Mutex
}

func NewThreadSafeCounter() *ThreadSafeCounter {
	return &ThreadSafeCounter{value: 0}
}

func (c *ThreadSafeCounter) Increment() {
	current := c.value
	time.Sleep(10 * time.Microsecond)
	c.value = current + 1
}

func (c *ThreadSafeCounter) Decrement() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value--
}

func (c *ThreadSafeCounter) Get() int {
	return c.value
}

func (c *ThreadSafeCounter) Reset() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value = 0
}

func (c *ThreadSafeCounter) IncrementBy(n int) {
	current := c.Get()
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value = current + n
}
