package solution

import (
	"math"
	"regexp"
	"sort"
	"strings"
)

type WordCount struct {
	Word  string
	Count int
}

type TextStats struct {
	WordCount       int
	SentenceCount   int
	AvgWordLength   float64
	MostCommonWords []WordCount
	UniqueWordCount int
}

func AnalyzeText(text string) TextStats {
	if strings.TrimSpace(text) == "" {
		return TextStats{
			WordCount:       0,
			SentenceCount:   0,
			AvgWordLength:   0.0,
			MostCommonWords: []WordCount{},
			UniqueWordCount: 0,
		}
	}

	wordRegex := regexp.MustCompile(`[a-zA-Z]+`)
	words := wordRegex.FindAllString(text, -1)

	wordCount := len(words)

	sentenceRegex := regexp.MustCompile(`[.!?]`)
	sentenceCount := len(sentenceRegex.FindAllString(text, -1))

	totalLength := 0
	for _, w := range words {
		totalLength += len(w)
	}
	avgWordLength := 0.0
	if wordCount > 0 {
		avgWordLength = math.Round(float64(totalLength)/float64(wordCount)*100) / 100
	}

	counter := make(map[string]int)
	for _, w := range words {
		lower := strings.ToLower(w)
		counter[lower]++
	}

	uniqueWordCount := len(counter)

	type pair struct {
		word  string
		count int
	}
	pairs := make([]pair, 0, len(counter))
	for word, count := range counter {
		pairs = append(pairs, pair{word, count})
	}

	sort.Slice(pairs, func(i, j int) bool {
		if pairs[i].count != pairs[j].count {
			return pairs[i].count > pairs[j].count
		}
		return pairs[i].word < pairs[j].word
	})

	mostCommon := make([]WordCount, 0, 5)
	for i := 0; i < len(pairs) && i < 5; i++ {
		mostCommon = append(mostCommon, WordCount{
			Word:  pairs[i].word,
			Count: pairs[i].count,
		})
	}

	return TextStats{
		WordCount:       wordCount,
		SentenceCount:   sentenceCount,
		AvgWordLength:   avgWordLength,
		MostCommonWords: mostCommon,
		UniqueWordCount: uniqueWordCount,
	}
}
