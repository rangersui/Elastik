package main

import (
	"log"

	"github.com/elastik/go/core"
)

// welcomeHTML is the onboarding renderer shown to first-time users.
// Source of truth: renderers/welcome/index.html (kept in sync manually).
const welcomeHTML = `<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>elastik</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#fafafa;color:#222;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh}
.hero{text-align:center;margin-bottom:48px}
.hero h1{font-size:1.4rem;font-weight:400;color:#666;margin-bottom:8px}
.hero p{font-size:0.9rem;color:#999}
.cards{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;margin-bottom:48px}
.card{width:160px;padding:28px 16px;border:1px solid #e0e0e0;border-radius:12px;background:#fff;text-align:center;cursor:pointer;transition:border-color .15s,box-shadow .15s}
.card:hover{border-color:#111;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.card .icon{font-size:1.8rem;margin-bottom:12px}
.card .label{font-size:0.95rem;font-weight:500}
.card .desc{font-size:0.75rem;color:#999;margin-top:6px}
.help-toggle{font-size:0.8rem;color:#aaa;cursor:pointer;border:none;background:none;padding:4px 8px}
.help-toggle:hover{color:#666}
.ai-box{display:none;margin-top:12px;width:340px;max-width:90vw}
.ai-box.open{display:flex;gap:8px}
.ai-box input{flex:1;padding:8px 12px;border:1px solid #ddd;border-radius:8px;font-size:0.85rem;outline:none}
.ai-box button{padding:8px 14px;border:none;border-radius:8px;background:#111;color:#fff;cursor:pointer;font-size:0.85rem}
</style>
</head>
<body>

<div class="hero">
  <h1>这是你的空间</h1>
  <p>选择一个模板开始，或创建空白页面</p>
</div>

<div class="cards">
  <div class="card" onclick="startNotes()">
    <div class="icon">&#128221;</div>
    <div class="label">笔记</div>
    <div class="desc">开始记录想法</div>
  </div>
  <div class="card" onclick="startTodo()">
    <div class="icon">&#9745;</div>
    <div class="label">待办</div>
    <div class="desc">管理你的任务</div>
  </div>
  <div class="card" onclick="startBlank()">
    <div class="icon">&#10010;</div>
    <div class="label">空白</div>
    <div class="desc">自定义页面</div>
  </div>
</div>

<button class="help-toggle" onclick="toggleHelp()">需要帮助?</button>
<div class="ai-box" id="aiBox">
  <input id="aiInput" placeholder="描述你想创建的内容..." onkeydown="if(event.key==='Enter')askAI()">
  <button onclick="askAI()">发送</button>
</div>

<script>
const E = window.__elastik;

async function startNotes() {
  await E.write('notes', '<h1>笔记</h1><p>开始写...</p>');
  window.location = '/notes';
}

async function startTodo() {
  await E.write('todo', '<h1>待办</h1><ul><li>第一件事</li></ul>');
  window.location = '/todo';
}

async function startBlank() {
  const name = prompt('页面名称 (英文字母、数字、横线):', '');
  if (!name || !name.trim()) return;
  const n = name.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
  if (!n) { alert('名称只能包含英文字母、数字、下划线和横线'); return; }
  await E.write(n, '');
  window.location = '/' + n;
}

function toggleHelp() {
  document.getElementById('aiBox').classList.toggle('open');
  const inp = document.getElementById('aiInput');
  if (inp.offsetParent) inp.focus();
}

async function askAI() {
  const inp = document.getElementById('aiInput');
  const q = inp.value.trim();
  if (!q) return;
  inp.value = '思考中...';
  inp.disabled = true;
  try {
    const r = await E.action('/ai/ask?world=default', q);
    if (r && typeof r === 'string') {
      await E.write('default', r);
    } else if (r && r.text) {
      await E.write('default', r.text);
    }
    window.location = '/default';
  } catch (e) {
    inp.disabled = false;
    inp.value = '';
    alert('AI 请求失败: ' + e.message);
  }
}
</script>
</body>
</html>`

// seedWelcome creates the welcome renderer and default world if no
// stages exist yet. This gives first-time users an onboarding screen
// instead of a blank page.
func seedWelcome(db *sqliteDB, key []byte) {
	stages, err := core.ListStages(db)
	if err != nil {
		log.Printf("  welcome: failed to list stages: %v", err)
		return
	}
	if len(stages) > 0 {
		return
	}

	// Create the renderer world with the welcome HTML.
	if _, err := core.WriteWorld(db, key, "renderers-welcome", welcomeHTML); err != nil {
		log.Printf("  welcome: failed to create renderers-welcome: %v", err)
		return
	}

	// Create default world pointing at the welcome renderer.
	if _, err := core.WriteWorld(db, key, "default", "<!--use:renderers-welcome-->"); err != nil {
		log.Printf("  welcome: failed to create default: %v", err)
		return
	}

	log.Printf("  welcome: seeded onboarding worlds")
}
