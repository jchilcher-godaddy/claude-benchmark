package solution

import (
	"strings"
	"testing"
	"time"
)

func TestShortenReturnsCode(t *testing.T) {
	s := NewURLShortener()
	code, err := s.Shorten("https://example.com")
	if err != nil {
		t.Fatalf("Shorten error: %v", err)
	}
	if code == "" || len(code) < 6 {
		t.Errorf("code = %q, want non-empty string with length >= 6", code)
	}
}

func TestResolveReturnsOriginal(t *testing.T) {
	s := NewURLShortener()
	code, _ := s.Shorten("https://example.com")
	url, err := s.Resolve(code)
	if err != nil {
		t.Fatalf("Resolve error: %v", err)
	}
	if url != "https://example.com" {
		t.Errorf("Resolve = %q, want %q", url, "https://example.com")
	}
}

func TestShortenSameURLReturnsSameCode(t *testing.T) {
	s := NewURLShortener()
	code1, _ := s.Shorten("https://example.com")
	code2, _ := s.Shorten("https://example.com")
	if code1 != code2 {
		t.Errorf("code1 = %q, code2 = %q, want same code", code1, code2)
	}
}

func TestShortenDifferentURLsReturnDifferentCodes(t *testing.T) {
	s := NewURLShortener()
	code1, _ := s.Shorten("https://example.com")
	code2, _ := s.Shorten("https://other.com")
	if code1 == code2 {
		t.Errorf("code1 = code2 = %q, want different codes", code1)
	}
}

func TestResolveNonexistentReturnsError(t *testing.T) {
	s := NewURLShortener()
	_, err := s.Resolve("nonexistent")
	if err == nil {
		t.Error("expected error for nonexistent code")
	}
}

func TestRejectsNoScheme(t *testing.T) {
	s := NewURLShortener()
	_, err := s.Shorten("example.com")
	if err == nil {
		t.Error("expected error for URL without scheme")
	}
}

func TestRejectsNoHost(t *testing.T) {
	s := NewURLShortener()
	_, err := s.Shorten("https://")
	if err == nil {
		t.Error("expected error for URL without host")
	}
}

func TestRejectsEmptyString(t *testing.T) {
	s := NewURLShortener()
	_, err := s.Shorten("")
	if err == nil {
		t.Error("expected error for empty string")
	}
}

func TestRejectsJavascriptScheme(t *testing.T) {
	s := NewURLShortener()
	_, err := s.Shorten("javascript:alert('xss')")
	if err == nil {
		t.Error("expected error for javascript scheme")
	}
	if !strings.Contains(strings.ToLower(err.Error()), "dangerous") &&
		!strings.Contains(strings.ToLower(err.Error()), "scheme") &&
		!strings.Contains(strings.ToLower(err.Error()), "javascript") {
		t.Errorf("error message = %q, want mention of dangerous/scheme/javascript", err.Error())
	}
}

func TestRejectsDataScheme(t *testing.T) {
	s := NewURLShortener()
	_, err := s.Shorten("data:text/html,<script>alert(1)</script>")
	if err == nil {
		t.Error("expected error for data scheme")
	}
}

func TestRejectsVBScriptScheme(t *testing.T) {
	s := NewURLShortener()
	_, err := s.Shorten("vbscript:MsgBox")
	if err == nil {
		t.Error("expected error for vbscript scheme")
	}
}

func TestStatsInitial(t *testing.T) {
	s := NewURLShortener()
	code, _ := s.Shorten("https://example.com")
	stats, err := s.GetStats(code)
	if err != nil {
		t.Fatalf("GetStats error: %v", err)
	}
	if stats.OriginalURL != "https://example.com" {
		t.Errorf("OriginalURL = %q, want %q", stats.OriginalURL, "https://example.com")
	}
	if stats.ClickCount != 0 {
		t.Errorf("ClickCount = %d, want 0", stats.ClickCount)
	}
	if stats.CreatedAt.IsZero() {
		t.Error("CreatedAt should not be zero")
	}
}

func TestStatsAfterResolves(t *testing.T) {
	s := NewURLShortener()
	code, _ := s.Shorten("https://example.com")
	s.Resolve(code)
	s.Resolve(code)
	s.Resolve(code)
	stats, _ := s.GetStats(code)
	if stats.ClickCount != 3 {
		t.Errorf("ClickCount = %d, want 3", stats.ClickCount)
	}
}

func TestStatsNonexistentReturnsError(t *testing.T) {
	s := NewURLShortener()
	_, err := s.GetStats("nonexistent")
	if err == nil {
		t.Error("expected error for nonexistent code")
	}
}

func TestDeleteExisting(t *testing.T) {
	s := NewURLShortener()
	code, _ := s.Shorten("https://example.com")
	deleted := s.Delete(code)
	if !deleted {
		t.Error("Delete should return true for existing code")
	}
}

func TestDeleteNonexistent(t *testing.T) {
	s := NewURLShortener()
	deleted := s.Delete("nonexistent")
	if deleted {
		t.Error("Delete should return false for nonexistent code")
	}
}

func TestResolveAfterDeleteReturnsError(t *testing.T) {
	s := NewURLShortener()
	code, _ := s.Shorten("https://example.com")
	s.Delete(code)
	_, err := s.Resolve(code)
	if err == nil {
		t.Error("expected error for deleted code")
	}
}

func TestCreatedAtIsRecent(t *testing.T) {
	s := NewURLShortener()
	before := time.Now()
	code, _ := s.Shorten("https://example.com")
	after := time.Now()
	stats, _ := s.GetStats(code)
	if stats.CreatedAt.Before(before) || stats.CreatedAt.After(after) {
		t.Errorf("CreatedAt = %v, want between %v and %v", stats.CreatedAt, before, after)
	}
}
