package solution

import (
	"sort"
	"testing"
)

func TestSimpleSentence(t *testing.T) {
	result := AnalyzeText("Hello world.")
	if result.WordCount != 2 {
		t.Errorf("WordCount = %d, want 2", result.WordCount)
	}
	if result.SentenceCount != 1 {
		t.Errorf("SentenceCount = %d, want 1", result.SentenceCount)
	}
	if result.AvgWordLength != 5.0 {
		t.Errorf("AvgWordLength = %f, want 5.0", result.AvgWordLength)
	}
	if result.UniqueWordCount != 2 {
		t.Errorf("UniqueWordCount = %d, want 2", result.UniqueWordCount)
	}
}

func TestMultiSentence(t *testing.T) {
	result := AnalyzeText("Hello world! How are you? I am fine.")
	if result.WordCount != 8 {
		t.Errorf("WordCount = %d, want 8", result.WordCount)
	}
	if result.SentenceCount != 3 {
		t.Errorf("SentenceCount = %d, want 3", result.SentenceCount)
	}
	if result.UniqueWordCount != 8 {
		t.Errorf("UniqueWordCount = %d, want 8", result.UniqueWordCount)
	}
}

func TestEmptyString(t *testing.T) {
	result := AnalyzeText("")
	if result.WordCount != 0 {
		t.Errorf("WordCount = %d, want 0", result.WordCount)
	}
	if result.SentenceCount != 0 {
		t.Errorf("SentenceCount = %d, want 0", result.SentenceCount)
	}
	if result.AvgWordLength != 0.0 {
		t.Errorf("AvgWordLength = %f, want 0.0", result.AvgWordLength)
	}
	if len(result.MostCommonWords) != 0 {
		t.Errorf("MostCommonWords length = %d, want 0", len(result.MostCommonWords))
	}
	if result.UniqueWordCount != 0 {
		t.Errorf("UniqueWordCount = %d, want 0", result.UniqueWordCount)
	}
}

func TestPunctuationHeavy(t *testing.T) {
	result := AnalyzeText("Hello world today is a nice day.")
	if result.WordCount != 7 {
		t.Errorf("WordCount = %d, want 7", result.WordCount)
	}
	found := false
	for _, wc := range result.MostCommonWords {
		if wc.Word == "hello" || wc.Word == "day" {
			found = true
			break
		}
	}
	if !found {
		t.Error("Expected 'hello' or 'day' in most common words")
	}
}

func TestCaseInsensitive(t *testing.T) {
	result := AnalyzeText("Hello HELLO hello World world.")
	if result.UniqueWordCount != 2 {
		t.Errorf("UniqueWordCount = %d, want 2", result.UniqueWordCount)
	}
	if len(result.MostCommonWords) < 2 {
		t.Fatalf("Expected at least 2 most common words")
	}
	if result.MostCommonWords[0].Word != "hello" || result.MostCommonWords[0].Count != 3 {
		t.Errorf("MostCommonWords[0] = %+v, want {hello 3}", result.MostCommonWords[0])
	}
	if result.MostCommonWords[1].Word != "world" || result.MostCommonWords[1].Count != 2 {
		t.Errorf("MostCommonWords[1] = %+v, want {world 2}", result.MostCommonWords[1])
	}
}

func TestTiebreakingAlphabetical(t *testing.T) {
	result := AnalyzeText("zebra apple banana zebra apple banana cat cat")
	tiedWords := []string{}
	for _, wc := range result.MostCommonWords {
		if wc.Count == 2 {
			tiedWords = append(tiedWords, wc.Word)
		}
	}
	sortedTied := make([]string, len(tiedWords))
	copy(sortedTied, tiedWords)
	sort.Strings(sortedTied)
	for i := range tiedWords {
		if tiedWords[i] != sortedTied[i] {
			t.Errorf("Tied words not in alphabetical order: %v", tiedWords)
			break
		}
	}
}

func TestAverageWordLength(t *testing.T) {
	result := AnalyzeText("Hi hello world.")
	if result.AvgWordLength != 4.0 {
		t.Errorf("AvgWordLength = %f, want 4.0", result.AvgWordLength)
	}
}

func TestUnicodeAccented(t *testing.T) {
	result := AnalyzeText("cafe resume naive.")
	if result.WordCount != 3 {
		t.Errorf("WordCount = %d, want 3", result.WordCount)
	}
	if result.SentenceCount != 1 {
		t.Errorf("SentenceCount = %d, want 1", result.SentenceCount)
	}
}

func TestOnlyPunctuation(t *testing.T) {
	result := AnalyzeText("... !!! ???")
	if result.WordCount != 0 {
		t.Errorf("WordCount = %d, want 0", result.WordCount)
	}
	if result.AvgWordLength != 0.0 {
		t.Errorf("AvgWordLength = %f, want 0.0", result.AvgWordLength)
	}
}

func TestSingleCharacter(t *testing.T) {
	result := AnalyzeText("I.")
	if result.WordCount != 1 {
		t.Errorf("WordCount = %d, want 1", result.WordCount)
	}
	if result.AvgWordLength != 1.0 {
		t.Errorf("AvgWordLength = %f, want 1.0", result.AvgWordLength)
	}
}

func TestVeryLongWord(t *testing.T) {
	longWord := ""
	for i := 0; i < 1000; i++ {
		longWord += "a"
	}
	result := AnalyzeText(longWord + " short.")
	if result.WordCount != 2 {
		t.Errorf("WordCount = %d, want 2", result.WordCount)
	}
	if result.AvgWordLength != 502.5 {
		t.Errorf("AvgWordLength = %f, want 502.5", result.AvgWordLength)
	}
}
