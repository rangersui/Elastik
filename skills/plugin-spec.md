# elastik plugin spec v1

一个 plugin 是一个 .py 文件在 plugins/ 目录下。

## 必须声明

```python
ROUTES = ["/path"]               # 要注册的路由
AUTH = "none" | "auth" | "approve"  # 权限级别
```

## 必须实现

```python
async def handle(method, body, params):
    # method: GET/POST/PUT/DELETE/PROPFIND/...
    # body:   请求体字符串 (已 decode)
    # params: query string dict + _scope
    # 返回:
    #   {...}             → 自动 json.dumps
    #   {"_html": str}    → text/html
    #   {"_body": str, "_ct": "..."} → 自定义 content-type
    #   {"_status": int}  → 自定义状态码
    #   {"_redirect": str} → 302
    #   {"_headers": [[k,v], ...]} → 自定义响应头
    return {"ok": True}
```

## server.py 保证

- AUTH 检查在调 handle 之前完成
- plugin 不需要 import 任何 auth 函数
- plugin 不需要检查 token
- body 大小已限制 (MAX_BODY)
- 路径已验证 (无 .. 和 //)

## plugin 不能做

- 不能修改 server.py 的全局状态
- 不能直接调 send/receive
- 不能自己检查 auth（重复且会漏）
- 不能注册 /stages /read /write 等核心路由

## 核心路由（server.py 永久持有，不可 plugin 化）

```
/<world>/read
/<world>/write
/<world>/append
/<world>/pending
/<world>/result
/<world>/clear
/<world>/sync
/stages
/  → index.html
```

## 一切其他路由都是 plugin

权限在内核不在应用。应用自己检查一定会漏。内核统一检查不可能漏。
