// AI bridge — built into the Go binary. No plugin, no Python.
//
// Startup detection order (first match wins):
//  1. Ollama at OLLAMA_HOST (default http://localhost:11434)
//  2. ANTHROPIC_API_KEY → Claude API
//  3. OPENAI_API_KEY    → OpenAI API
//  4. DEEPSEEK_API_KEY  → DeepSeek API (OpenAI-compatible)
//  5. GOOGLE_API_KEY    → Google Gemini API
//  6. Nothing           → print install hint
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
	Provider string `json:"provider"` // "ollama", "claude", "openai", "deepseek", "google", "none"
	Model    string `json:"model"`
	Status   string `json:"status"` // "connected", "no provider"
	Hint     string `json:"hint,omitempty"`
	baseURL  string
	apiKey   string
}

var aiClient = &http.Client{Timeout: 120 * time.Second}

// ─── detection ──────────────────────────────────────────────────────

func detectAI() aiConfig {
	// 1. Ollama (local — lowest latency, no API key needed)
	host := env("OLLAMA_HOST", "http://localhost:11434")
	if models := probeOllama(host); len(models) > 0 {
		model := resolveModel(env("OLLAMA_MODEL", ""), models)
		log.Printf("  ai: ollama at %s (%s)", host, model)
		return aiConfig{
			Provider: "ollama", Model: model, Status: "connected",
			baseURL: host,
		}
	}

	// 2. Anthropic (Claude)
	if key := os.Getenv("ANTHROPIC_API_KEY"); key != "" {
		model := env("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
		log.Printf("  ai: Claude API (%s)", model)
		return aiConfig{
			Provider: "claude", Model: model, Status: "connected",
			baseURL: "https://api.anthropic.com", apiKey: key,
		}
	}

	// 3. OpenAI
	if key := os.Getenv("OPENAI_API_KEY"); key != "" {
		model := env("OPENAI_MODEL", "gpt-4o-mini")
		log.Printf("  ai: OpenAI API (%s)", model)
		return aiConfig{
			Provider: "openai", Model: model, Status: "connected",
			baseURL: "https://api.openai.com", apiKey: key,
		}
	}

	// 4. DeepSeek (OpenAI-compatible)
	if key := os.Getenv("DEEPSEEK_API_KEY"); key != "" {
		model := env("DEEPSEEK_MODEL", "deepseek-chat")
		log.Printf("  ai: DeepSeek API (%s)", model)
		return aiConfig{
			Provider: "deepseek", Model: model, Status: "connected",
			baseURL: "https://api.deepseek.com", apiKey: key,
		}
	}

	// 5. Google (Gemini)
	if key := os.Getenv("GOOGLE_API_KEY"); key != "" {
		model := env("GOOGLE_MODEL", "gemini-2.0-flash")
		log.Printf("  ai: Google Gemini API (%s)", model)
		return aiConfig{
			Provider: "google", Model: model, Status: "connected",
			baseURL: "https://generativelanguage.googleapis.com", apiKey: key,
		}
	}

	// 6. Nothing
	hint := "curl -fsSL https://ollama.com/install.sh | sh && ollama pull gemma3:4b"
	log.Printf("  ai: no provider detected")
	log.Printf("  ai: to add AI → %s", hint)
	log.Printf("  ai: or set ANTHROPIC_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY / GOOGLE_API_KEY")
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
	case "openai":
		response, err = askOpenAICompat(s.ai.baseURL, s.ai.apiKey, s.ai.Model, fullPrompt)
	case "deepseek":
		response, err = askOpenAICompat(s.ai.baseURL, s.ai.apiKey, s.ai.Model, fullPrompt)
	case "google":
		response, err = askGoogle(s.ai.baseURL, s.ai.apiKey, s.ai.Model, fullPrompt)
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

// ─── OpenAI-compatible API (OpenAI, DeepSeek) ──────────────────────

func askOpenAICompat(baseURL, apiKey, model, prompt string) (string, error) {
	body, _ := json.Marshal(map[string]any{
		"model":      model,
		"max_tokens": 4096,
		"messages":   []map[string]string{{"role": "user", "content": prompt}},
	})
	req, _ := http.NewRequest("POST", baseURL+"/v1/chat/completions", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	resp, err := aiClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("openai-compat: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		b, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("openai-compat: %s %s", resp.Status, string(b))
	}
	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("openai-compat: %w", err)
	}
	if len(result.Choices) == 0 {
		return "", fmt.Errorf("openai-compat: empty response")
	}
	return result.Choices[0].Message.Content, nil
}

// ─── Google Gemini API ──────────────────────────────────────────────

func askGoogle(baseURL, apiKey, model, prompt string) (string, error) {
	body, _ := json.Marshal(map[string]any{
		"contents": []map[string]any{
			{"parts": []map[string]string{{"text": prompt}}},
		},
	})
	url := fmt.Sprintf("%s/v1beta/models/%s:generateContent?key=%s", baseURL, model, apiKey)
	req, _ := http.NewRequest("POST", url, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	resp, err := aiClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("google: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		b, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("google: %s %s", resp.Status, string(b))
	}
	var result struct {
		Candidates []struct {
			Content struct {
				Parts []struct {
					Text string `json:"text"`
				} `json:"parts"`
			} `json:"content"`
		} `json:"candidates"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("google: %w", err)
	}
	if len(result.Candidates) == 0 || len(result.Candidates[0].Content.Parts) == 0 {
		return "", fmt.Errorf("google: empty response")
	}
	return result.Candidates[0].Content.Parts[0].Text, nil
}
