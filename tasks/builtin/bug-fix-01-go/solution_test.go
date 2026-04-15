package solution

import "testing"

func TestEmptyArray(t *testing.T) {
	result := BinarySearch([]int{}, 5)
	if result != -1 {
		t.Errorf("BinarySearch([], 5) = %d, want -1", result)
	}
}

func TestSingleElementFound(t *testing.T) {
	result := BinarySearch([]int{5}, 5)
	if result != 0 {
		t.Errorf("BinarySearch([5], 5) = %d, want 0", result)
	}
}

func TestSingleElementNotFound(t *testing.T) {
	result := BinarySearch([]int{5}, 3)
	if result != -1 {
		t.Errorf("BinarySearch([5], 3) = %d, want -1", result)
	}
}

func TestFirstElement(t *testing.T) {
	result := BinarySearch([]int{1, 2, 3, 4, 5}, 1)
	if result != 0 {
		t.Errorf("BinarySearch([1,2,3,4,5], 1) = %d, want 0", result)
	}
}

func TestLastElement(t *testing.T) {
	result := BinarySearch([]int{1, 2, 3, 4, 5}, 5)
	if result != 4 {
		t.Errorf("BinarySearch([1,2,3,4,5], 5) = %d, want 4", result)
	}
}

func TestMiddleElement(t *testing.T) {
	result := BinarySearch([]int{1, 2, 3, 4, 5}, 3)
	if result != 2 {
		t.Errorf("BinarySearch([1,2,3,4,5], 3) = %d, want 2", result)
	}
}

func TestNotFound(t *testing.T) {
	result := BinarySearch([]int{1, 2, 3, 4, 5}, 6)
	if result != -1 {
		t.Errorf("BinarySearch([1,2,3,4,5], 6) = %d, want -1", result)
	}
}

func TestNotFoundBetween(t *testing.T) {
	result := BinarySearch([]int{1, 3, 5, 7, 9}, 4)
	if result != -1 {
		t.Errorf("BinarySearch([1,3,5,7,9], 4) = %d, want -1", result)
	}
}

func TestLargeArray(t *testing.T) {
	arr := make([]int, 1000)
	for i := range arr {
		arr[i] = i * 2
	}
	result := BinarySearch(arr, 500)
	if result != 250 {
		t.Errorf("BinarySearch(large_array, 500) = %d, want 250", result)
	}
}

func TestTwoElements(t *testing.T) {
	result := BinarySearch([]int{1, 2}, 2)
	if result != 1 {
		t.Errorf("BinarySearch([1,2], 2) = %d, want 1", result)
	}
}

func TestNegativeNumbers(t *testing.T) {
	result := BinarySearch([]int{-5, -3, -1, 0, 2, 4}, -3)
	if result != 1 {
		t.Errorf("BinarySearch([-5,-3,-1,0,2,4], -3) = %d, want 1", result)
	}
}

func TestDuplicates(t *testing.T) {
	arr := []int{1, 2, 2, 2, 3, 4}
	result := BinarySearch(arr, 2)
	if result < 1 || result > 3 {
		t.Errorf("BinarySearch([1,2,2,2,3,4], 2) = %d, want index in range [1,3]", result)
	}
}
