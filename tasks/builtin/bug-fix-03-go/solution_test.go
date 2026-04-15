package solution

import (
	"sync"
	"testing"
)

func TestBasicOperations(t *testing.T) {
	counter := NewThreadSafeCounter()
	counter.Increment()
	if counter.Get() != 1 {
		t.Errorf("Get() = %d, want 1", counter.Get())
	}
	counter.Decrement()
	if counter.Get() != 0 {
		t.Errorf("Get() = %d, want 0", counter.Get())
	}
}

func TestReset(t *testing.T) {
	counter := NewThreadSafeCounter()
	counter.Increment()
	counter.Increment()
	counter.Reset()
	if counter.Get() != 0 {
		t.Errorf("Get() after Reset() = %d, want 0", counter.Get())
	}
}

func TestIncrementBy(t *testing.T) {
	counter := NewThreadSafeCounter()
	counter.IncrementBy(5)
	if counter.Get() != 5 {
		t.Errorf("Get() = %d, want 5", counter.Get())
	}
	counter.IncrementBy(3)
	if counter.Get() != 8 {
		t.Errorf("Get() = %d, want 8", counter.Get())
	}
}

func TestConcurrentIncrements(t *testing.T) {
	counter := NewThreadSafeCounter()
	var wg sync.WaitGroup
	iterations := 100
	goroutines := 10

	for i := 0; i < goroutines; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < iterations; j++ {
				counter.Increment()
			}
		}()
	}

	wg.Wait()
	expected := goroutines * iterations
	if counter.Get() != expected {
		t.Errorf("Get() = %d, want %d", counter.Get(), expected)
	}
}

func TestConcurrentDecrements(t *testing.T) {
	counter := NewThreadSafeCounter()
	iterations := 100
	goroutines := 10
	counter.IncrementBy(goroutines * iterations)

	var wg sync.WaitGroup
	for i := 0; i < goroutines; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < iterations; j++ {
				counter.Decrement()
			}
		}()
	}

	wg.Wait()
	if counter.Get() != 0 {
		t.Errorf("Get() = %d, want 0", counter.Get())
	}
}

func TestConcurrentMixed(t *testing.T) {
	counter := NewThreadSafeCounter()
	var wg sync.WaitGroup
	iterations := 50

	wg.Add(2)
	go func() {
		defer wg.Done()
		for i := 0; i < iterations; i++ {
			counter.Increment()
		}
	}()
	go func() {
		defer wg.Done()
		for i := 0; i < iterations; i++ {
			counter.Decrement()
		}
	}()

	wg.Wait()
	result := counter.Get()
	if result < -iterations || result > iterations {
		t.Errorf("Get() = %d, out of expected range [%d, %d]", result, -iterations, iterations)
	}
}

func TestConcurrentIncrementBy(t *testing.T) {
	counter := NewThreadSafeCounter()
	var wg sync.WaitGroup
	goroutines := 10
	incrementValue := 5

	for i := 0; i < goroutines; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			counter.IncrementBy(incrementValue)
		}()
	}

	wg.Wait()
	expected := goroutines * incrementValue
	if counter.Get() != expected {
		t.Errorf("Get() = %d, want %d", counter.Get(), expected)
	}
}

func TestConcurrentReset(t *testing.T) {
	counter := NewThreadSafeCounter()
	var wg sync.WaitGroup

	wg.Add(2)
	go func() {
		defer wg.Done()
		for i := 0; i < 100; i++ {
			counter.Increment()
		}
	}()
	go func() {
		defer wg.Done()
		for i := 0; i < 10; i++ {
			counter.Reset()
		}
	}()

	wg.Wait()
	result := counter.Get()
	if result < 0 || result > 100 {
		t.Errorf("Get() = %d, out of expected range [0, 100]", result)
	}
}

func TestConcurrentGetDoesNotRace(t *testing.T) {
	counter := NewThreadSafeCounter()
	var wg sync.WaitGroup

	wg.Add(2)
	go func() {
		defer wg.Done()
		for i := 0; i < 100; i++ {
			counter.Increment()
		}
	}()
	go func() {
		defer wg.Done()
		for i := 0; i < 100; i++ {
			_ = counter.Get()
		}
	}()

	wg.Wait()
}

func TestHighConcurrency(t *testing.T) {
	counter := NewThreadSafeCounter()
	var wg sync.WaitGroup
	goroutines := 100
	iterations := 100

	for i := 0; i < goroutines; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < iterations; j++ {
				counter.Increment()
			}
		}()
	}

	wg.Wait()
	expected := goroutines * iterations
	if counter.Get() != expected {
		t.Errorf("Get() = %d, want %d (possible race condition)", counter.Get(), expected)
	}
}
