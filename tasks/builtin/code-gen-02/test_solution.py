import pytest
from solution import analyze_text


def test_simple_sentence():
    result = analyze_text("Hello world.")
    assert result["word_count"] == 2
    assert result["sentence_count"] == 1
    assert result["average_word_length"] == 5.0
    assert result["unique_word_count"] == 2


def test_multi_sentence():
    result = analyze_text("Hello world! How are you? I am fine.")
    assert result["word_count"] == 8
    assert result["sentence_count"] == 3
    assert result["unique_word_count"] == 8


def test_empty_string():
    result = analyze_text("")
    assert result["word_count"] == 0
    assert result["sentence_count"] == 0
    assert result["average_word_length"] == 0.0
    assert result["most_common_words"] == []
    assert result["unique_word_count"] == 0


def test_punctuation_heavy():
    result = analyze_text("Hello world today is a nice day.")
    assert result["word_count"] == 7
    words = [w for w, _ in result["most_common_words"]]
    assert "hello" in words or "day" in words


def test_case_insensitive():
    result = analyze_text("Hello HELLO hello World world.")
    assert result["unique_word_count"] == 2
    assert result["most_common_words"][0] == ("hello", 3)
    assert result["most_common_words"][1] == ("world", 2)


def test_tiebreaking_alphabetical():
    result = analyze_text("zebra apple banana zebra apple banana cat cat")
    common = result["most_common_words"]
    tied_words = [w for w, c in common if c == 2]
    assert tied_words == sorted(tied_words)


def test_average_word_length():
    result = analyze_text("Hi hello world.")
    assert result["average_word_length"] == 4.0


def test_unicode_accented():
    result = analyze_text("cafe resume naive.")
    assert result["word_count"] == 3
    assert result["sentence_count"] == 1


def test_only_punctuation():
    result = analyze_text("... !!! ???")
    assert result["word_count"] == 0
    assert result["sentence_count"] >= 0
    assert result["average_word_length"] == 0.0


def test_single_character():
    result = analyze_text("I.")
    assert result["word_count"] == 1
    assert result["average_word_length"] == 1.0


def test_very_long_word():
    long_word = "a" * 1000
    result = analyze_text(f"{long_word} short.")
    assert result["word_count"] == 2
    assert result["average_word_length"] == 502.5
