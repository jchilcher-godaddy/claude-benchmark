package solution

import "testing"

func TestBaseCaseZero(t *testing.T) {
	result, err := Fibonacci(0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 0 {
		t.Errorf("Fibonacci(0) = %d, want 0", result)
	}
}

func TestBaseCaseOne(t *testing.T) {
	result, err := Fibonacci(1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 1 {
		t.Errorf("Fibonacci(1) = %d, want 1", result)
	}
}

func TestSmallFibonacci(t *testing.T) {
	result, err := Fibonacci(10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 55 {
		t.Errorf("Fibonacci(10) = %d, want 55", result)
	}
}

func TestLargerFibonacci(t *testing.T) {
	result, err := Fibonacci(20)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 6765 {
		t.Errorf("Fibonacci(20) = %d, want 6765", result)
	}
}

func TestNegativeReturnsError(t *testing.T) {
	_, err := Fibonacci(-1)
	if err == nil {
		t.Error("expected error for negative input")
	}
}

func TestLargeFibonacci(t *testing.T) {
	result, err := Fibonacci(50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 12586269025 {
		t.Errorf("Fibonacci(50) = %d, want 12586269025", result)
	}
}

func TestSequenceConsistency(t *testing.T) {
	for n := 2; n < 15; n++ {
		fn, _ := Fibonacci(n)
		fn1, _ := Fibonacci(n - 1)
		fn2, _ := Fibonacci(n - 2)
		if fn != fn1+fn2 {
			t.Errorf("Fibonacci(%d) = %d, want %d + %d = %d", n, fn, fn1, fn2, fn1+fn2)
		}
	}
}

func TestSmallValues(t *testing.T) {
	expected := map[int]int{2: 1, 3: 2, 4: 3, 5: 5, 6: 8, 7: 13}
	for n, want := range expected {
		got, err := Fibonacci(n)
		if err != nil {
			t.Fatalf("Fibonacci(%d) error: %v", n, err)
		}
		if got != want {
			t.Errorf("Fibonacci(%d) = %d, want %d", n, got, want)
		}
	}
}

func TestVeryLarge(t *testing.T) {
	result, err := Fibonacci(90)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 2880067194370816120 {
		t.Errorf("Fibonacci(90) = %d, want 2880067194370816120", result)
	}
}

func TestNegativeVarious(t *testing.T) {
	for _, n := range []int{-5, -100} {
		_, err := Fibonacci(n)
		if err == nil {
			t.Errorf("expected error for Fibonacci(%d)", n)
		}
	}
}

func TestFibonacci30(t *testing.T) {
	result, err := Fibonacci(30)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 832040 {
		t.Errorf("Fibonacci(30) = %d, want 832040", result)
	}
}
