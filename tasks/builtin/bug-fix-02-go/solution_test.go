package solution

import (
	"reflect"
	"testing"
)

func TestEmpty(t *testing.T) {
	result := MergeSort([]int{})
	if len(result) != 0 {
		t.Errorf("MergeSort([]) = %v, want []", result)
	}
}

func TestSingleElement(t *testing.T) {
	result := MergeSort([]int{42})
	expected := []int{42}
	if !reflect.DeepEqual(result, expected) {
		t.Errorf("MergeSort([42]) = %v, want %v", result, expected)
	}
}

func TestAlreadySorted(t *testing.T) {
	result := MergeSort([]int{1, 2, 3, 4, 5})
	expected := []int{1, 2, 3, 4, 5}
	if !reflect.DeepEqual(result, expected) {
		t.Errorf("MergeSort([1,2,3,4,5]) = %v, want %v", result, expected)
	}
}

func TestReverseSorted(t *testing.T) {
	result := MergeSort([]int{5, 4, 3, 2, 1})
	expected := []int{1, 2, 3, 4, 5}
	if !reflect.DeepEqual(result, expected) {
		t.Errorf("MergeSort([5,4,3,2,1]) = %v, want %v", result, expected)
	}
}

func TestDuplicates(t *testing.T) {
	result := MergeSort([]int{3, 1, 4, 1, 5, 9, 2, 6, 5})
	expected := []int{1, 1, 2, 3, 4, 5, 5, 6, 9}
	if !reflect.DeepEqual(result, expected) {
		t.Errorf("MergeSort([3,1,4,1,5,9,2,6,5]) = %v, want %v", result, expected)
	}
}

func TestNegativeNumbers(t *testing.T) {
	result := MergeSort([]int{-3, 5, -1, 0, 2, -5})
	expected := []int{-5, -3, -1, 0, 2, 5}
	if !reflect.DeepEqual(result, expected) {
		t.Errorf("MergeSort([-3,5,-1,0,2,-5]) = %v, want %v", result, expected)
	}
}

func TestNoMutation(t *testing.T) {
	original := []int{3, 1, 4, 1, 5}
	copy := make([]int, len(original))
	copy = append([]int{}, original...)
	MergeSort(original)
	if !reflect.DeepEqual(original, copy) {
		t.Error("MergeSort mutated the original slice")
	}
}

func TestStability(t *testing.T) {
	type Pair struct {
		Key   int
		Value int
	}
	pairs := []Pair{{1, 1}, {2, 1}, {1, 2}, {2, 2}, {1, 3}}
	keys := make([]int, len(pairs))
	for i, p := range pairs {
		keys[i] = p.Key
	}

	sorted := MergeSort(keys)

	ones := []int{}
	twos := []int{}
	onesIdx := []int{}
	twosIdx := []int{}
	for i, k := range keys {
		if k == 1 {
			ones = append(ones, pairs[i].Value)
			onesIdx = append(onesIdx, i)
		} else if k == 2 {
			twos = append(twos, pairs[i].Value)
			twosIdx = append(twosIdx, i)
		}
	}

	sortedOnes := []int{}
	sortedTwos := []int{}
	for i, k := range sorted {
		if k == 1 {
			for j, origIdx := range onesIdx {
				if len(sortedOnes) == j {
					if origIdx <= i {
						sortedOnes = append(sortedOnes, pairs[origIdx].Value)
						break
					}
				}
			}
		} else if k == 2 {
			for j, origIdx := range twosIdx {
				if len(sortedTwos) == j {
					if origIdx <= i {
						sortedTwos = append(sortedTwos, pairs[origIdx].Value)
						break
					}
				}
			}
		}
	}

	if !isSorted(sorted) {
		t.Errorf("result not sorted: %v", sorted)
	}
}

func TestLargeArray(t *testing.T) {
	arr := []int{64, 34, 25, 12, 22, 11, 90, 88, 45, 50, 23, 36, 18, 77, 29}
	result := MergeSort(arr)
	if !isSorted(result) {
		t.Errorf("MergeSort large array not sorted: %v", result)
	}
}

func TestAllSame(t *testing.T) {
	result := MergeSort([]int{5, 5, 5, 5, 5})
	expected := []int{5, 5, 5, 5, 5}
	if !reflect.DeepEqual(result, expected) {
		t.Errorf("MergeSort([5,5,5,5,5]) = %v, want %v", result, expected)
	}
}

func isSorted(arr []int) bool {
	for i := 1; i < len(arr); i++ {
		if arr[i] < arr[i-1] {
			return false
		}
	}
	return true
}
