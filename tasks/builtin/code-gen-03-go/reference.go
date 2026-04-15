package solution

import (
	"container/list"
	"errors"
)

type entry struct {
	key   string
	value interface{}
}

type LRUCache struct {
	capacity int
	cache    map[string]*list.Element
	order    *list.List
}

func NewLRUCache(capacity int) (*LRUCache, error) {
	if capacity < 1 {
		return nil, errors.New("capacity must be at least 1")
	}
	return &LRUCache{
		capacity: capacity,
		cache:    make(map[string]*list.Element),
		order:    list.New(),
	}, nil
}

func (c *LRUCache) Get(key string) (interface{}, error) {
	elem, exists := c.cache[key]
	if !exists {
		return nil, errors.New("key not found")
	}
	c.order.MoveToFront(elem)
	return elem.Value.(*entry).value, nil
}

func (c *LRUCache) Put(key string, value interface{}) {
	if elem, exists := c.cache[key]; exists {
		c.order.MoveToFront(elem)
		elem.Value.(*entry).value = value
		return
	}

	elem := c.order.PushFront(&entry{key: key, value: value})
	c.cache[key] = elem

	if c.order.Len() > c.capacity {
		oldest := c.order.Back()
		if oldest != nil {
			c.order.Remove(oldest)
			delete(c.cache, oldest.Value.(*entry).key)
		}
	}
}

func (c *LRUCache) Delete(key string) bool {
	elem, exists := c.cache[key]
	if !exists {
		return false
	}
	c.order.Remove(elem)
	delete(c.cache, key)
	return true
}

func (c *LRUCache) Len() int {
	return len(c.cache)
}

func (c *LRUCache) Contains(key string) bool {
	_, exists := c.cache[key]
	return exists
}

func (c *LRUCache) Keys() []string {
	keys := make([]string, 0, c.order.Len())
	for elem := c.order.Front(); elem != nil; elem = elem.Next() {
		keys = append(keys, elem.Value.(*entry).key)
	}
	return keys
}
