"""AI bridge for elastik Python server. Mirrors go/native/ai.go."""
import json, os, urllib.request, urllib.error

def _env(key, default=""):
    return os.environ.get(key, default) or default

def _probe_ollama(host):
    """Return list of model names from ollama, or [] on failure."""
    try:
        req = urllib.request.Request(host + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

def _resolve_model(wanted, available):
    if not wanted:
        return available[0]
    if wanted in available:
        return wanted
    for m in available:
        if m.startswith(wanted):
            return m
    print(f"  ai: OLLAMA_MODEL={wanted!r} not found, using {available[0]}")
    return available[0]

def detect_ai():
    """Detect AI provider. Returns dict with provider/model/status/hint + internal keys."""
    # 1. Ollama
    host = _env("OLLAMA_HOST", "http://localhost:11434")
    models = _probe_ollama(host)
    if models:
        model = _resolve_model(_env("OLLAMA_MODEL"), models)
        print(f"  ai: ollama at {host} ({model})")
        return {"provider": "ollama", "model": model, "status": "connected",
                "_base_url": host, "_api_key": ""}

    # 2. Anthropic (Claude)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        model = _env("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        print(f"  ai: Claude API ({model})")
        return {"provider": "claude", "model": model, "status": "connected",
                "_base_url": "https://api.anthropic.com", "_api_key": key}

    # 3. OpenAI
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        model = _env("OPENAI_MODEL", "gpt-4o-mini")
        print(f"  ai: OpenAI API ({model})")
        return {"provider": "openai", "model": model, "status": "connected",
                "_base_url": "https://api.openai.com", "_api_key": key}

    # 4. DeepSeek
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        model = _env("DEEPSEEK_MODEL", "deepseek-chat")
        print(f"  ai: DeepSeek API ({model})")
        return {"provider": "deepseek", "model": model, "status": "connected",
                "_base_url": "https://api.deepseek.com", "_api_key": key}

    # 5. Google Gemini
    key = os.environ.get("GOOGLE_API_KEY", "")
    if key:
        model = _env("GOOGLE_MODEL", "gemini-2.0-flash")
        print(f"  ai: Google Gemini API ({model})")
        return {"provider": "google", "model": model, "status": "connected",
                "_base_url": "https://generativelanguage.googleapis.com", "_api_key": key}

    # 6. Nothing
    hint = "curl -fsSL https://ollama.com/install.sh | sh && ollama pull gemma3:4b"
    print("  ai: no provider detected")
    print(f"  ai: to add AI -> {hint}")
    print("  ai: or set ANTHROPIC_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY / GOOGLE_API_KEY")
    return {"provider": "none", "model": "", "status": "no provider", "hint": hint,
            "_base_url": "", "_api_key": ""}

def _post_json(url, data, headers=None, timeout=120):
    """POST JSON, return parsed response or raise."""
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

def _ask_ollama(base_url, model, prompt):
    r = _post_json(base_url + "/api/generate",
                   {"model": model, "prompt": prompt, "stream": False})
    return r.get("response", "")

def _ask_claude(api_key, model, prompt):
    r = _post_json("https://api.anthropic.com/v1/messages",
                   {"model": model, "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]},
                   {"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    parts = r.get("content", [])
    if not parts:
        raise ValueError("claude: empty response")
    return parts[0].get("text", "")

def _ask_openai_compat(base_url, api_key, model, prompt):
    r = _post_json(base_url + "/v1/chat/completions",
                   {"model": model, "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]},
                   {"Authorization": "Bearer " + api_key})
    choices = r.get("choices", [])
    if not choices:
        raise ValueError("openai-compat: empty response")
    return choices[0].get("message", {}).get("content", "")

def _ask_google(base_url, api_key, model, prompt):
    url = f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}"
    r = _post_json(url, {"contents": [{"parts": [{"text": prompt}]}]})
    cands = r.get("candidates", [])
    if not cands or not cands[0].get("content", {}).get("parts", []):
        raise ValueError("google: empty response")
    return cands[0]["content"]["parts"][0].get("text", "")

def ask_ai(cfg, prompt):
    """Send prompt to the detected provider. Returns response text."""
    p = cfg["provider"]
    base, key, model = cfg["_base_url"], cfg["_api_key"], cfg["model"]
    if p == "ollama":
        return _ask_ollama(base, model, prompt)
    if p == "claude":
        return _ask_claude(key, model, prompt)
    if p in ("openai", "deepseek"):
        return _ask_openai_compat(base, key, model, prompt)
    if p == "google":
        return _ask_google(base, key, model, prompt)
    raise ValueError("no AI provider configured")

def status_json(cfg):
    """Return the public-safe status dict (no keys/urls)."""
    out = {"provider": cfg["provider"], "model": cfg["model"], "status": cfg["status"]}
    if cfg.get("hint"):
        out["hint"] = cfg["hint"]
    return out
