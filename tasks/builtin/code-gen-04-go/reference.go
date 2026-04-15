package solution

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"net/url"
	"strings"
	"time"
)

type Stats struct {
	OriginalURL string
	ClickCount  int
	CreatedAt   time.Time
}

type entry struct {
	originalURL string
	clickCount  int
	createdAt   time.Time
}

type URLShortener struct {
	urlToCode   map[string]string
	codeToEntry map[string]*entry
}

var dangerousSchemes = map[string]bool{
	"javascript": true,
	"data":       true,
	"vbscript":   true,
}

func NewURLShortener() *URLShortener {
	return &URLShortener{
		urlToCode:   make(map[string]string),
		codeToEntry: make(map[string]*entry),
	}
}

func (s *URLShortener) validateURL(urlStr string) error {
	if urlStr == "" {
		return errors.New("URL must be a non-empty string")
	}
	parsed, err := url.Parse(urlStr)
	if err != nil {
		return fmt.Errorf("invalid URL: %w", err)
	}
	if parsed.Scheme == "" || parsed.Host == "" {
		return fmt.Errorf("invalid URL: missing scheme or host: %q", urlStr)
	}
	if dangerousSchemes[strings.ToLower(parsed.Scheme)] {
		return fmt.Errorf("dangerous URL scheme: %q", parsed.Scheme)
	}
	return nil
}

func (s *URLShortener) generateCode(urlStr string, attempt int) string {
	data := fmt.Sprintf("%s:%d", urlStr, attempt)
	hash := sha256.Sum256([]byte(data))
	return fmt.Sprintf("%x", hash[:4])
}

func (s *URLShortener) Shorten(urlStr string) (string, error) {
	if err := s.validateURL(urlStr); err != nil {
		return "", err
	}

	if code, exists := s.urlToCode[urlStr]; exists {
		return code, nil
	}

	attempt := 0
	code := s.generateCode(urlStr, attempt)
	for s.codeToEntry[code] != nil {
		attempt++
		code = s.generateCode(urlStr, attempt)
	}

	s.codeToEntry[code] = &entry{
		originalURL: urlStr,
		clickCount:  0,
		createdAt:   time.Now(),
	}
	s.urlToCode[urlStr] = code
	return code, nil
}

func (s *URLShortener) Resolve(shortCode string) (string, error) {
	entry, exists := s.codeToEntry[shortCode]
	if !exists {
		return "", fmt.Errorf("short code not found: %q", shortCode)
	}
	entry.clickCount++
	return entry.originalURL, nil
}

func (s *URLShortener) GetStats(shortCode string) (Stats, error) {
	entry, exists := s.codeToEntry[shortCode]
	if !exists {
		return Stats{}, fmt.Errorf("short code not found: %q", shortCode)
	}
	return Stats{
		OriginalURL: entry.originalURL,
		ClickCount:  entry.clickCount,
		CreatedAt:   entry.createdAt,
	}, nil
}

func (s *URLShortener) Delete(shortCode string) bool {
	entry, exists := s.codeToEntry[shortCode]
	if !exists {
		return false
	}
	delete(s.codeToEntry, shortCode)
	delete(s.urlToCode, entry.originalURL)
	return true
}
