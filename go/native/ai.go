// AI bridge — built into the Go binary. No plugin, no Python.
//
// Startup detection order:
//  1. ANTHROPIC_API_KEY → Claude API
//  2. Ollama at OLLAMA_HOST (default http://localhost:11434)
//  3. Nothing → print install hint
//
// Routes:
//  POST /ai/ask?world={name}  → send prompt to AI, return response
//  GET  /ai/status            → provider, model, status
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/elastik/go/core"
)

// aiConfig describes the detected AI provider. Only exported fields
// are included in /ai/status JSON; baseURL and apiKey stay private.
type aiConfig struct {
	Provider string `json:"provider"` // "ollama", "claude", "none"
	Model    string `json:"model"`
	Status   string `json:"status"` // "connected", "no provider"
	Hint     string `json:"hint,omitempty"`
	baseURL  string
	apiKey   string
}

var aiClient = &http.Client{Timeout: 120 * time.Second}

// ─── detection ──────────────────────────────────────────────────────

func detectAI() aiConfig {
	// 1. Claude API key
	if key := os.Getenv("ANTHROPIC_API_KEY"); key != "" {
		model := env("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
		log.Printf("  ai: Claude API (%s)", model)
		return aiConfig{
			Provider: "claude", Model: model, Status: "connected",
			apiKey: key,
		}
	}

	// 2. Ollama
	host := env("OLLAMA_HOST", "http://localhost:11434")
	if models := probeOllama(host); len(models) > 0 {
		model := resolveModel(env("OLLAMA_MODEL", ""), models)
		log.Printf("  ai: ollama at %s (%s)", host, model)
		return aiConfig{
			Provider: "ollama", Model: model, Status: "connected",
			baseURL: host,
		}
	}

	// 3. Nothing
	hint := "curl -fsSL https://ollama.com/install.sh | sh && ollama pull gemma3:4b"
	log.Printf("  ai: no provider detected")
	log.Printf("  ai: to add AI → %s", hint)
	log.Printf("  ai: or set ANTHROPIC_API_KEY for Claude")
	return aiConfig{Provider: "none", Status: "no provider", Hint: hint}
}

// resolveModel picks the right model name. The env var OLLAMA_MODEL
// may be a short name like "qwen2.5:1.5b" while ollama registers the
// full quantized name "qwen2.5:1.5b-instruct-q4_K_M". Try exact
// match, then prefix match, then fall back to the first available.
func resolveModel(wanted string, available []string) string {
	if wanted == "" {
		return available[0]
	}
	for _, m := range available {
		if m == wanted {
			return wanted
		}
	}
	for _, m := range available {
		if strings.HasPrefix(m, wanted) {
			return m
		}
	}
	log.Printf("  ai: OLLAMA_MODEL=%q not found, using %s", wanted, available[0])
	return available[0]
}

func probeOllama(host string) []string {
	c := &http.Client{Timeout: 2 * time.Second}
	resp, err := c.Get(host + "/api/tags")
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil
	}
	var result struct {
		Models []struct {
			Name string `json:"name"`
		} `json:"models"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil
	}
	out := make([]string, len(result.Models))
	for i, m := range result.Models {
		out[i] = m.Name
	}
	return out
}

// ─── handlers ───────────────────────────────────────────────────────

func (s *server) handleAIStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, 200, s.ai)
}

func (s *server) handleAIAsk(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeErr(w, 405, "method not allowed")
		return
	}
	if s.ai.Provider == "none" {
		writeErr(w, 503, "no AI provider — install ollama or set ANTHROPIC_API_KEY")
		return
	}

	prompt, err := readBody(r)
	if err != nil {
		writeErr(w, 413, "body too large")
		return
	}
	if prompt == "" {
		writeErr(w, 400, "empty prompt")
		return
	}

	// If ?world= is set, read the world's content as context.
	worldName := r.URL.Query().Get("world")
	fullPrompt := prompt
	if worldName != "" {
		if stage, err := core.ReadWorld(s.db, worldName); err == nil && stage.StageHTML != "" {
			fullPrompt = "Current content of this world:\n\n" + stage.StageHTML + "\n\n---\n\nUser request: " + prompt
		}
	}

	var response string
	switch s.ai.Provider {
	case "ollama":
		response, err = askOllama(s.ai.baseURL, s.ai.Model, fullPrompt)
	case "claude":
		response, err = askClaude(s.ai.apiKey, s.ai.Model, fullPrompt)
	}
	if err != nil {
		writeErr(w, 502, fmt.Sprintf("ai: %v", err))
		return
	}

	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(200)
	_, _ = w.Write([]byte(response))
}

// ─── ollama ─────────────────────────────────────────────────────────

func askOllama(host, model, prompt string) (string, error) {
	body, _ := json.Marshal(map[string]any{
		"model":  model,
		"prompt": prompt,
		"stream": false,
	})
	resp, err := aiClient.Post(host+"/api/generate", "application/json", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("ollama: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		b, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("ollama: %s %s", resp.Status, string(b))
	}
	var result struct {
		Response string `json:"response"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("ollama: %w", err)
	}
	return result.Response, nil
}

// ─── claude API ─────────────────────────────────────────────────────

func askClaude(apiKey, model, prompt string) (string, error) {
	body, _ := json.Marshal(map[string]any{
		"model":      model,
		"max_tokens": 4096,
		"messages":   []map[string]string{{"role": "user", "content": prompt}},
	})
	req, _ := http.NewRequest("POST", "https://api.anthropic.com/v1/messages", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-api-key", apiKey)
	req.Header.Set("anthropic-version", "2023-06-01")

	resp, err := aiClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("claude: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		b, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("claude: %s %s", resp.Status, string(b))
	}
	var result struct {
		Content []struct {
			Text string `json:"text"`
		} `json:"content"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("claude: %w", err)
	}
	if len(result.Content) == 0 {
		return "", fmt.Errorf("claude: empty response")
	}
	return result.Content[0].Text, nil
}
