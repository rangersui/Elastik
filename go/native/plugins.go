package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// Plugin protocol (5 rules):
// 1. Plugin is an executable in plugins/
// 2. plugin --routes → JSON array of routes it handles
// 3. Request: stdin one line JSON {"path","method","body","query"}
// 4. Response: stdout one line JSON {"status","body"}
// 5. Exit 0 → normal, non-zero → 502

type pluginReq struct {
	Path   string `json:"path"`
	Method string `json:"method"`
	Body   string `json:"body"`
	Query  string `json:"query,omitempty"`
}

type pluginResp struct {
	Status int    `json:"status"`
	Body   string `json:"body"`
	CT     string `json:"content_type,omitempty"`
}

// routeTable maps route path → plugin executable path.
var routeTable = map[string]string{}

// pluginCmd builds an exec.Cmd for a plugin. .py files run via python.
func pluginCmd(path string, args ...string) *exec.Cmd {
	if strings.HasSuffix(path, ".py") {
		return exec.Command("python", append([]string{"-u", path}, args...)...)
	}
	return exec.Command(path, args...)
}

// pluginExec runs a plugin with args and returns stdout. Stderr silenced.
func pluginExec(path string, args ...string) ([]byte, error) {
	cmd := pluginCmd(path, args...)
	cmd.Stderr = nil // suppress noise from non-CGI plugins
	return cmd.Output()
}

// scanPlugins runs executables in plugins/ and plugins/available/ with --routes.
func scanPlugins() {
	for _, dir := range []string{"plugins", filepath.Join("plugins", "available")} {
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, e := range entries {
			if e.IsDir() || strings.HasPrefix(e.Name(), ".") || strings.HasPrefix(e.Name(), "_") {
				continue
			}
			skip := false
			for _, ext := range []string{".md", ".txt", ".json", ".lock", ".cmd", ".bat"} {
				if strings.HasSuffix(e.Name(), ext) {
					skip = true
					break
				}
			}
			if skip {
				continue
			}
			p := filepath.Join(dir, e.Name())
			out, err := pluginExec(p, "--routes")
			if err != nil {
				continue
			}
			var routes []string
			if json.Unmarshal([]byte(strings.TrimSpace(string(out))), &routes) != nil {
				continue
			}
			// Don't register if route already claimed by plugins/ (override).
			for _, r := range routes {
				if _, exists := routeTable[r]; !exists {
					routeTable[r] = p
				}
			}
			log.Printf("  plugin: %s → %v", e.Name(), routes)
		}
	}
}

// servePlugin dispatches an HTTP request to the plugin executable.
func servePlugin(w http.ResponseWriter, r *http.Request, pluginPath, route string) {
	var body string
	if r.Method == http.MethodPost {
		r.Body = http.MaxBytesReader(nil, r.Body, maxBody)
		b, err := readBody(r)
		if err != nil {
			writeErr(w, 413, "body too large")
			return
		}
		body = b
	}

	reqJSON, _ := json.Marshal(pluginReq{
		Path:   route,
		Method: r.Method,
		Body:   body,
		Query:  r.URL.RawQuery,
	})

	cmd := pluginCmd(pluginPath)
	cmd.Stdin = strings.NewReader(string(reqJSON) + "\n")
	cmd.Stderr = os.Stderr
	out, err := cmd.Output()
	if err != nil {
		log.Printf("  plugin %s: %v", filepath.Base(pluginPath), err)
		writeErr(w, 502, "plugin error")
		return
	}
	out = []byte(strings.TrimSpace(string(out))) // strip \r\n from Windows .cmd

	var resp pluginResp
	if json.Unmarshal(out, &resp) != nil {
		// Not JSON → raw text response.
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(200)
		_, _ = w.Write(out)
		return
	}

	ct := resp.CT
	if ct == "" {
		ct = "application/json"
	}
	status := resp.Status
	if status == 0 {
		status = 200
	}
	w.Header().Set("Content-Type", ct)
	w.WriteHeader(status)
	_, _ = w.Write([]byte(resp.Body))
}
