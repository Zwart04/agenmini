package proxy

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	// DefaultOpenCodeUA is the official OpenCode fingerprint User-Agent.
	// Upstream requires version >= 1.17.0 (PR #4105, PR #4111).
	DefaultOpenCodeUA = "opencode/1.18.31 ai-sdk/provider-utils/4.0.46 runtime/bun/1.3.14"

	base62Chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)

// OpenCodeSessionRegex matches canonical OpenCode session IDs: ses_ + 12 hex + 14 Base62 (30 chars).
var OpenCodeSessionRegex = regexp.MustCompile(`^ses_[0-9a-f]{12}[0-9A-Za-z]{14}$`)

// OpenCodeRequestRegex matches canonical OpenCode request IDs: msg_ + 12 hex + 14 Base62 (30 chars).
var OpenCodeRequestRegex = regexp.MustCompile(`^msg_[0-9a-f]{12}[0-9A-Za-z]{14}$`)

var (
	sessionMu      sync.Mutex
	lastTimestamp  int64
	sessionCounter uint64
)

func unstableRandomBase62(n int) string {
	b := make([]byte, n)
	_, _ = rand.Read(b)
	var sb strings.Builder
	sb.Grow(n)
	for _, v := range b {
		sb.WriteByte(base62Chars[int(v)%62])
	}
	return sb.String()
}

// GenerateOpenCodeSessionID generates a descending canonical OpenCode session ID (30 chars).
func GenerateOpenCodeSessionID() string {
	sessionMu.Lock()
	now := time.Now().UnixMilli()
	if now != lastTimestamp {
		lastTimestamp = now
		sessionCounter = 0
	}
	sessionCounter++
	counter := sessionCounter
	sessionMu.Unlock()

	current := uint64(now)*0x1000 + (counter & 0xfff)
	value := ^current
	var timeBytes [6]byte
	for i := range 6 {
		timeBytes[i] = byte((value >> (40 - 8*uint64(i))) & 0xff)
	}
	return "ses_" + hex.EncodeToString(timeBytes[:]) + unstableRandomBase62(14)
}

// GenerateOpenCodeRequestID generates a canonical OpenCode request ID (30 chars).
func GenerateOpenCodeRequestID() string {
	now := time.Now().UnixMilli()
	current := uint64(now)*0x1000 + 1
	var timeBytes [6]byte
	for i := range 6 {
		timeBytes[i] = byte((current >> (40 - 8*uint64(i))) & 0xff)
	}
	return "msg_" + hex.EncodeToString(timeBytes[:]) + unstableRandomBase62(14)
}

// GenerateOpenCodeProjectID generates a canonical 40-char hex project ID (PR #4111).
func GenerateOpenCodeProjectID() string {
	b := make([]byte, 20)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// TranslateOpenCodeSessionID deterministically maps foreign sessions to valid 30-char canonical IDs.
func TranslateOpenCodeSessionID(sessionID, clientTool string) string {
	trimmed := strings.TrimSpace(sessionID)
	if OpenCodeSessionRegex.MatchString(trimmed) {
		return trimmed
	}
	tool := clientTool
	if tool == "" {
		tool = "generic"
	}
	h := sha256.New()
	h.Write([]byte("opencode\x00" + tool + "\x00" + trimmed))
	digest := h.Sum(nil)
	timeHex := hex.EncodeToString(digest[:6])
	var sb strings.Builder
	sb.Grow(14)
	for i := 6; i < 20; i++ {
		sb.WriteByte(base62Chars[int(digest[i])%62])
	}
	return "ses_" + timeHex + sb.String()
}

var opencodeUARegex = regexp.MustCompile(`(?i)opencode/(\d+)\.(\d+)(?:\.(\d+))?`)

// HasValidOpenCodeVersion checks if a User-Agent is opencode >= 1.17.0.
func HasValidOpenCodeVersion(ua string) bool {
	matches := opencodeUARegex.FindStringSubmatch(ua)
	if len(matches) < 3 {
		return false
	}
	major, err := strconv.Atoi(matches[1])
	if err != nil {
		return false
	}
	minor, err := strconv.Atoi(matches[2])
	if err != nil {
		return false
	}
	return major > 1 || (major == 1 && minor >= 17)
}

// BuildOpenCodeHeaders generates the official OpenCode fingerprint headers to prevent 403 FreeTierError.
func BuildOpenCodeHeaders(rawHeaders map[string]string, sessionID string, isStream bool) map[string]string {
	var session string
	if sessionID != "" {
		session = TranslateOpenCodeSessionID(sessionID, "")
	} else {
		session = GenerateOpenCodeSessionID()
	}

	res := map[string]string{
		"Content-Type":       "application/json",
		"Authorization":      "Bearer public",
		"x-api-key":          "public",
		"User-Agent":         DefaultOpenCodeUA,
		"x-opencode-client":  "cli",
		"x-opencode-session": session,
		"x-opencode-request": GenerateOpenCodeRequestID(),
		"x-opencode-project": GenerateOpenCodeProjectID(),
	}
	if isStream {
		res["Accept"] = "text/event-stream"
	} else {
		res["Accept"] = "*/*"
	}
	for _, h := range []string{"x-relay-target", "x-relay-path"} {
		if v, ok := rawHeaders[h]; ok {
			res[h] = v
		}
	}
	for k, v := range rawHeaders {
		lk := strings.ToLower(k)
		if lk == "user-agent" && HasValidOpenCodeVersion(v) {
			res["User-Agent"] = v
		}
		if lk == "x-opencode-session" {
			trimmed := strings.TrimSpace(v)
			if OpenCodeSessionRegex.MatchString(trimmed) {
				res["x-opencode-session"] = trimmed
			} else if trimmed != "" {
				res["x-opencode-session"] = TranslateOpenCodeSessionID(trimmed, "")
			}
		}
		if lk == "x-opencode-client" || lk == "x-opencode-request" {
			res[k] = v
		}
		if lk == "x-opencode-project" {
			trimmed := strings.TrimSpace(v)
			if trimmed != "" && trimmed != "global" {
				res["x-opencode-project"] = trimmed
			}
		}
	}
	return res
}
