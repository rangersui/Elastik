// MCP (Model Context Protocol) stdio server.
//
// When the binary is launched with --mcp, it speaks JSON-RPC 2.0 over
// stdin/stdout instead of starting an HTTP server. Claude Desktop (or
// any MCP client) can then use elastik worlds + AI as tools.
//
// Claude Desktop config (claude_desktop_config.json):
//
//	{
//	  "mcpServers": {
//	    "elastik": {
//	      "command": "path/to/elastik-go",
//	      "args": ["--mcp"]
//	    }
//	  }
//	}
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log"
	"os"

	"github.com/elastik/go/core"
)

// ─── JSON-RPC 2.0 types ────────────────────────────────────────────

type jsonRPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      any             `json:"id,omitempty"` // number or string; nil for notifications
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type jsonRPCResponse struct {
	JSONRPC string    `json:"jsonrpc"`
	ID      any       `json:"id,omitempty"`
	Result  any       `json:"result,omitempty"`
	Error   *rpcError `json:"error,omitempty"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// ─── MCP protocol types ────────────────────────────────────────────

type mcpToolDef struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	InputSchema any    `json:"inputSchema"`
}

type mcpToolResult struct {
	Content []mcpContent `json:"content"`
	IsError bool         `json:"isError,omitempty"`
}

type mcpContent struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

// ─── tool definitions ──────────────────────────────────────────────

func mcpTools(hasAI bool) []mcpToolDef {
	tools := []mcpToolDef{
		{
			Name:        "list_worlds",
			Description: "List all elastik worlds (stages) with their versions.",
			InputSchema: map[string]any{
				"type":       "object",
				"properties": map[string]any{},
			},
		},
		{
			Name:        "read_world",
			Description: "Read the content of an elastik world.",
			InputSchema: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"world": map[string]any{
						"type":        "string",
						"description": "World name (e.g. 'work', 'home')",
					},
				},
				"required": []string{"world"},
			},
		},
		{
			Name:        "write_world",
			Description: "Overwrite the entire content of an elastik world. Creates the world if it doesn't exist.",
			InputSchema: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"world": map[string]any{
						"type":        "string",
						"description": "World name",
					},
					"content": map[string]any{
						"type":        "string",
						"description": "New content (HTML or plain text)",
					},
				},
				"required": []string{"world", "content"},
			},
		},
		{
			Name:        "append_world",
			Description: "Append content to the end of an elastik world. Creates the world if it doesn't exist.",
			InputSchema: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"world": map[string]any{
						"type":        "string",
						"description": "World name",
					},
					"content": map[string]any{
						"type":        "string",
						"description": "Content to append",
					},
				},
				"required": []string{"world", "content"},
			},
		},
	}

	if hasAI {
		tools = append(tools, mcpToolDef{
			Name:        "ask_ai",
			Description: "Send a prompt to the configured AI provider (ollama, Claude, OpenAI, DeepSeek, or Gemini). Optionally include a world's content as context.",
			InputSchema: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"prompt": map[string]any{
						"type":        "string",
						"description": "The prompt to send to AI",
					},
					"world": map[string]any{
						"type":        "string",
						"description": "Optional world name — its content is prepended as context",
					},
				},
				"required": []string{"prompt"},
			},
		})
	}

	return tools
}

// ─── MCP main loop ─────────────────────────────────────────────────

func runMCP(cfg config) {
	db := newSQLiteDB(cfg.dataDir)
	ai := detectAI()

	log.SetOutput(os.Stderr) // MCP uses stdout for JSON-RPC; logs go to stderr
	log.Printf("  mcp: elastik MCP server ready (ai: %s)", ai.Provider)

	scanner := bufio.NewScanner(os.Stdin)
	// MCP messages can be large (world content); grow buffer to 10 MB.
	scanner.Buffer(make([]byte, 64*1024), 10*1024*1024)

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var req jsonRPCRequest
		if err := json.Unmarshal(line, &req); err != nil {
			writeRPC(jsonRPCResponse{
				JSONRPC: "2.0",
				Error:   &rpcError{Code: -32700, Message: "parse error"},
			})
			continue
		}

		// Notifications (no id) — just acknowledge silently.
		if req.ID == nil {
			// "initialized", "notifications/cancelled", etc.
			continue
		}

		resp := handleMCPRequest(db, cfg.key, ai, req)
		resp.JSONRPC = "2.0"
		resp.ID = req.ID
		writeRPC(resp)
	}
}

func writeRPC(resp jsonRPCResponse) {
	b, _ := json.Marshal(resp)
	fmt.Fprintf(os.Stdout, "%s\n", b)
}

func handleMCPRequest(db *sqliteDB, key []byte, ai aiConfig, req jsonRPCRequest) jsonRPCResponse {
	switch req.Method {
	case "initialize":
		return jsonRPCResponse{Result: map[string]any{
			"protocolVersion": "2024-11-05",
			"capabilities": map[string]any{
				"tools": map[string]any{},
			},
			"serverInfo": map[string]any{
				"name":    "elastik",
				"version": "2.1.0",
			},
		}}

	case "tools/list":
		return jsonRPCResponse{Result: map[string]any{
			"tools": mcpTools(ai.Provider != "none"),
		}}

	case "tools/call":
		return handleToolCall(db, key, ai, req.Params)

	case "ping":
		return jsonRPCResponse{Result: map[string]any{}}

	default:
		return jsonRPCResponse{Error: &rpcError{
			Code: -32601, Message: "method not found: " + req.Method,
		}}
	}
}

// ─── tool dispatch ─────────────────────────────────────────────────

func handleToolCall(db *sqliteDB, key []byte, ai aiConfig, raw json.RawMessage) jsonRPCResponse {
	var params struct {
		Name      string          `json:"name"`
		Arguments json.RawMessage `json:"arguments"`
	}
	if err := json.Unmarshal(raw, &params); err != nil {
		return jsonRPCResponse{Error: &rpcError{Code: -32602, Message: "invalid params"}}
	}

	var args map[string]string
	if params.Arguments != nil {
		_ = json.Unmarshal(params.Arguments, &args)
	}
	if args == nil {
		args = map[string]string{}
	}

	switch params.Name {
	case "list_worlds":
		return mcpListWorlds(db)
	case "read_world":
		return mcpReadWorld(db, args["world"])
	case "write_world":
		return mcpWriteWorld(db, key, args["world"], args["content"])
	case "append_world":
		return mcpAppendWorld(db, key, args["world"], args["content"])
	case "ask_ai":
		return mcpAskAI(db, ai, args["prompt"], args["world"])
	default:
		return toolError("unknown tool: " + params.Name)
	}
}

// ─── tool implementations ──────────────────────────────────────────

func mcpListWorlds(db *sqliteDB) jsonRPCResponse {
	list, err := core.ListStages(db)
	if err != nil {
		return toolError(err.Error())
	}
	if list == nil {
		list = []core.StageInfo{}
	}
	b, _ := json.MarshalIndent(list, "", "  ")
	return toolOK(string(b))
}

func mcpReadWorld(db *sqliteDB, world string) jsonRPCResponse {
	if world == "" {
		return toolError("missing required argument: world")
	}
	stage, err := core.ReadWorld(db, world)
	if err != nil {
		return toolError(err.Error())
	}
	b, _ := json.MarshalIndent(stage, "", "  ")
	return toolOK(string(b))
}

func mcpWriteWorld(db *sqliteDB, key []byte, world, content string) jsonRPCResponse {
	if world == "" {
		return toolError("missing required argument: world")
	}
	v, err := core.WriteWorld(db, key, world, content)
	if err != nil {
		return toolError(err.Error())
	}
	return toolOK(fmt.Sprintf("written to %s (version %d)", world, v))
}

func mcpAppendWorld(db *sqliteDB, key []byte, world, content string) jsonRPCResponse {
	if world == "" {
		return toolError("missing required argument: world")
	}
	v, err := core.AppendWorld(db, key, world, content)
	if err != nil {
		return toolError(err.Error())
	}
	return toolOK(fmt.Sprintf("appended to %s (version %d)", world, v))
}

func mcpAskAI(db *sqliteDB, ai aiConfig, prompt, world string) jsonRPCResponse {
	if prompt == "" {
		return toolError("missing required argument: prompt")
	}
	if ai.Provider == "none" {
		return toolError("no AI provider configured")
	}

	fullPrompt := prompt
	if world != "" {
		if stage, err := core.ReadWorld(db, world); err == nil && stage.StageHTML != "" {
			fullPrompt = "Current content of this world:\n\n" + stage.StageHTML + "\n\n---\n\nUser request: " + prompt
		}
	}

	var response string
	var err error
	switch ai.Provider {
	case "ollama":
		response, err = askOllama(ai.baseURL, ai.Model, fullPrompt)
	case "claude":
		response, err = askClaude(ai.apiKey, ai.Model, fullPrompt)
	case "openai":
		response, err = askOpenAICompat(ai.baseURL, ai.apiKey, ai.Model, fullPrompt)
	case "deepseek":
		response, err = askOpenAICompat(ai.baseURL, ai.apiKey, ai.Model, fullPrompt)
	case "google":
		response, err = askGoogle(ai.baseURL, ai.apiKey, ai.Model, fullPrompt)
	}
	if err != nil {
		return toolError(err.Error())
	}
	return toolOK(response)
}

// ─── helpers ───────────────────────────────────────────────────────

func toolOK(text string) jsonRPCResponse {
	return jsonRPCResponse{Result: mcpToolResult{
		Content: []mcpContent{{Type: "text", Text: text}},
	}}
}

func toolError(msg string) jsonRPCResponse {
	return jsonRPCResponse{Result: mcpToolResult{
		Content: []mcpContent{{Type: "text", Text: "Error: " + msg}},
		IsError: true,
	}}
}
