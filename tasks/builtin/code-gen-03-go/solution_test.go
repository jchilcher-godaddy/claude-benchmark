package solution

import (
	"testing"
)

func TestBasicGetPut(t *testing.T) {
	cache, _ := NewLRUCache(2)
	cache.Put("a", 1)
	cache.Put("b", 2)
	val, err := cache.Get("a")
	if err != nil || val != 1 {
		t.Errorf("Get(a) = %v, %v, want 1, nil", val, err)
	}
	val, err = cache.Get("b")
	if err != nil || val != 2 {
		t.Errorf("Get(b) = %v, %v, want 2, nil", val, err)
	}
}

func TestEviction(t *testing.T) {
	cache, _ := NewLRUCache(2)
	cache.Put("a", 1)
	cache.Put("b", 2)
	cache.Put("c", 3)
	if cache.Contains("a") {
		t.Error("Expected 'a' to be evicted")
	}
	val, _ := cache.Get("b")
	if val != 2 {
		t.Errorf("Get(b) = %v, want 2", val)
	}
	val, _ = cache.Get("c")
	if val != 3 {
		t.Errorf("Get(c) = %v, want 3", val)
	}
}

func TestAccessOrder(t *testing.T) {
	cache, _ := NewLRUCache(3)
	cache.Put("a", 1)
	cache.Put("b", 2)
	cache.Put("c", 3)
	cache.Get("a")
	cache.Put("d", 4)
	if cache.Contains("b") {
		t.Error("Expected 'b' to be evicted")
	}
	if !cache.Contains("a") {
		t.Error("Expected 'a' to still be in cache")
	}
}

func TestUpdateExisting(t *testing.T) {
	cache, _ := NewLRUCache(2)
	cache.Put("a", 1)
	cache.Put("b", 2)
	cache.Put("a", 10)
	cache.Put("c", 3)
	if cache.Contains("b") {
		t.Error("Expected 'b' to be evicted")
	}
	val, _ := cache.Get("a")
	if val != 10 {
		t.Errorf("Get(a) = %v, want 10", val)
	}
}

func TestDelete(t *testing.T) {
	cache, _ := NewLRUCache(2)
	cache.Put("a", 1)
	if !cache.Delete("a") {
		t.Error("Delete(a) should return true")
	}
	if cache.Contains("a") {
		t.Error("'a' should not be in cache after delete")
	}
	if cache.Delete("a") {
		t.Error("Delete(a) should return false for non-existent key")
	}
}

func TestLen(t *testing.T) {
	cache, _ := NewLRUCache(3)
	if cache.Len() != 0 {
		t.Errorf("Len() = %d, want 0", cache.Len())
	}
	cache.Put("a", 1)
	if cache.Len() != 1 {
		t.Errorf("Len() = %d, want 1", cache.Len())
	}
	cache.Put("b", 2)
	if cache.Len() != 2 {
		t.Errorf("Len() = %d, want 2", cache.Len())
	}
	cache.Put("c", 3)
	cache.Put("d", 4)
	if cache.Len() != 3 {
		t.Errorf("Len() = %d, want 3", cache.Len())
	}
}

func TestContains(t *testing.T) {
	cache, _ := NewLRUCache(2)
	cache.Put("a", 1)
	if !cache.Contains("a") {
		t.Error("Contains(a) should be true")
	}
	if cache.Contains("b") {
		t.Error("Contains(b) should be false")
	}
}

func TestKeysMRUOrder(t *testing.T) {
	cache, _ := NewLRUCache(3)
	cache.Put("a", 1)
	cache.Put("b", 2)
	cache.Put("c", 3)
	keys := cache.Keys()
	expected := []string{"c", "b", "a"}
	if !sliceEqual(keys, expected) {
		t.Errorf("Keys() = %v, want %v", keys, expected)
	}
	cache.Get("a")
	keys = cache.Keys()
	expected = []string{"a", "c", "b"}
	if !sliceEqual(keys, expected) {
		t.Errorf("Keys() after Get(a) = %v, want %v", keys, expected)
	}
}

func TestCapacityOne(t *testing.T) {
	cache, _ := NewLRUCache(1)
	cache.Put("a", 1)
	cache.Put("b", 2)
	if cache.Contains("a") {
		t.Error("Expected 'a' to be evicted")
	}
	val, _ := cache.Get("b")
	if val != 2 {
		t.Errorf("Get(b) = %v, want 2", val)
	}
}

func TestInvalidCapacity(t *testing.T) {
	_, err := NewLRUCache(0)
	if err == nil {
		t.Error("Expected error for capacity 0")
	}
	_, err = NewLRUCache(-1)
	if err == nil {
		t.Error("Expected error for capacity -1")
	}
}

func TestGetNonexistent(t *testing.T) {
	cache, _ := NewLRUCache(2)
	_, err := cache.Get("missing")
	if err == nil {
		t.Error("Expected error for nonexistent key")
	}
}

func sliceEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
