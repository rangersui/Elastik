# Captive Portal Deployment

Use WiFi captive portal detection to auto-launch elastik on any device that connects to your network.

## Prerequisites

- A router running Linux (OpenWrt, Raspberry Pi, any Linux box acting as AP)
- `bus.py` or `server.py` running on the router
- Router controls DHCP and DNS for the network

## How it works

1. Device connects to WiFi
2. OS sends an HTTP probe to a known URL:
   - iOS/macOS: `http://captive.apple.com/hotspot-detect.html`
   - Android: `http://connectivitycheck.gstatic.com/generate_204`
   - Windows: `http://www.msftconnecttest.com/connecttest.txt`
3. Router intercepts port 80 traffic, returns 302 redirect to elastik
4. OS detects the redirect, opens a built-in webview
5. Webview loads elastik — user sees worlds, not a login page

The device thinks it needs to "sign in to WiFi". What it actually gets is elastik.

## Setup: iptables

Redirect all port 80 traffic to elastik:

```bash
# Replace 192.168.8.1 with your router's IP, 3005 with elastik port
iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 80 \
  -j DNAT --to-destination 192.168.8.1:3005

# Allow return traffic
iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE
```

To let authenticated devices bypass (real captive portal behavior):

```bash
# Mark authenticated MACs
iptables -t nat -A PREROUTING -i wlan0 -m mac --mac-source AA:BB:CC:DD:EE:FF \
  -p tcp --dport 80 -j ACCEPT

# Everyone else gets redirected
iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 80 \
  -j DNAT --to-destination 192.168.8.1:3005
```

## Setup: dnsmasq

Hijack all DNS or just the probe domains:

```conf
# Option A: all domains resolve to router (full hijack)
address=/#/192.168.8.1

# Option B: only hijack probe domains (lighter touch)
address=/captive.apple.com/192.168.8.1
address=/connectivitycheck.gstatic.com/192.168.8.1
address=/www.msftconnecttest.com/192.168.8.1
address=/nmcheck.gnome.org/192.168.8.1
```

Option B is recommended. Devices detect the captive portal, pop the webview, but normal DNS still works.

## Captive portal webview limitations

The system webview that pops up is not a full browser:

| Capability | Status | Impact |
|-----------|--------|--------|
| DOM rendering | Yes | UI works |
| CSS | Yes | Styling works |
| JavaScript | Yes | Logic works |
| fetch/XHR | Yes | Can read/write worlds |
| WebGPU | No | No WebLLM |
| localStorage | Limited | State may not persist |
| IndexedDB | Limited | No model caching |
| Background | No | Closes when dismissed |
| Service Worker | No | No offline |

The webview is a thin client. It can read and write worlds, render HTML, run JS. It cannot do local AI inference. That's fine — the router is right there running server.py.

## Adaptive compute

The same bus.py serves both capable and limited clients:

```
Tesla browser (WebGPU)     → Tyrant mode  → browser runs WebLLM
Laptop Chrome (WebGPU)     → Tyrant mode  → browser runs WebLLM
Captive portal webview     → Normal mode  → server runs Ollama
IoT device curl            → API mode     → just GET/POST strings
```

`navigator.gpu` detection in index.html handles this automatically. No configuration needed.

## Security notes

- Captive portal intercepts **HTTP (port 80)** only, not HTTPS (443)
- Modern apps use HTTPS — their traffic passes through untouched
- Only the OS-level probe requests (which are HTTP by design) get redirected
- This is not traffic hijacking — it's using the WiFi standard's discovery mechanism as intended
- Auth token on bus.py controls who can write. Read is open by design.

## Digital territory

| WiFi concept | elastik analogy |
|-------------|-----------------|
| WiFi coverage area | Border |
| Captive portal | Customs |
| Auth token | Visa |
| Connecting to WiFi | Entry |
| Portal popup | Passport stamp |
| Disconnect | Exit |

Your WiFi range defines your digital territory. Anyone who enters gets elastik. What they can do inside depends on their auth token.
