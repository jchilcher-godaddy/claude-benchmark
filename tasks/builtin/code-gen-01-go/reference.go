package solution

import "errors"

func Fibonacci(n int) (int, error) {
	if n < 0 {
		return 0, errors.New("n must be non-negative")
	}
	if n == 0 {
		return 0, nil
	}
	if n == 1 {
		return 1, nil
	}
	prev, curr := 0, 1
	for i := 2; i <= n; i++ {
		prev, curr = curr, prev+curr
	}
	return curr, nil
}
