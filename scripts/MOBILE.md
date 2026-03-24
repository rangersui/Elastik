# Mobile Integration

## Apple Shortcuts (iOS)

No app needed. Use the built-in Shortcuts app.

### Quick Write shortcut:

1. Open Shortcuts app → + → New Shortcut
2. Add action: "Ask for Input" → type: Text → prompt: "What to write?"
3. Add action: "Get Contents of URL"
   → URL: http://100.x.x.x:3004/mobile/write
   → Method: POST
   → Headers: X-Auth-Token = your-token
   → Request Body: File → input from step 2
4. Done. Tap the shortcut → type anything → it's on your Stage.

### Quick Read shortcut:

1. Add action: "Get Contents of URL"
   → URL: http://100.x.x.x:3004/mobile/read
   → Method: GET
2. Add action: "Quick Look" → shows Stage content
3. Done. One tap to see what's on your wall.

### Siri trigger:

Rename shortcut to "Write to elastik"
→ "Hey Siri, write to elastik"
→ Siri asks what to write → you speak → POST to elastik
→ Your voice is now a string in universe.db.

### Share Sheet:

1. New Shortcut → enable "Show in Share Sheet"
2. Add action: "Get Contents of URL"
   → POST input text to /mobile/write
3. Any app → Share → "Write to elastik"
→ Article, photo URL, note, anything → into universe.db

## Android Tasker

1. New Task → HTTP Request action
   → Method: POST
   → URL: http://100.x.x.x:3004/mobile/write
   → Headers: X-Auth-Token=your-token
   → Body: %input
2. Trigger: widget / NFC tag / time / location / anything

## Requirements

- Tailscale on phone + server machine (same network)
- Or public URL via cloudflare tunnel
- elastik auth token

## Zero app. Zero install. Your OS is the client.
