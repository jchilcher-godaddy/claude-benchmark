import re
from collections import Counter


def analyze_text(text: str) -> dict:
    if not text.strip():
        return {
            "word_count": 0,
            "sentence_count": 0,
            "average_word_length": 0.0,
            "most_common_words": [],
            "unique_word_count": 0,
        }

    words = re.findall(r"[a-zA-Z]+", text)
    words_lower = [w.lower() for w in words]

    word_count = len(words)
    sentence_count = len(re.findall(r"[.!?]", text))
    average_word_length = round(sum(len(w) for w in words) / word_count, 2) if word_count > 0 else 0.0

    counter = Counter(words_lower)
    most_common = counter.most_common()
    most_common_sorted = sorted(most_common, key=lambda x: (-x[1], x[0]))[:5]

    unique_word_count = len(counter)

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "average_word_length": average_word_length,
        "most_common_words": most_common_sorted,
        "unique_word_count": unique_word_count,
    }
