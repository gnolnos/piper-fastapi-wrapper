# Piper FastAPI Wrapper — "MIỆNG" (TTS bridge)

A tiny **FastAPI HTTP wrapper around [Piper](https://github.com/OHF-Voice/piper1-gpl) TTS**
running over the [Wyoming protocol](https://github.com/rhasspy/wyoming).
Exposes a plain `text → WAV` HTTP API so any script, agent, or automation can
synthesize speech **without speaking the Wyoming TCP protocol**.

Built for the Z.O.L.A (Hermes agent) voice stack — Vietnamese-first, but Piper
supports 44+ languages via its voice set.

## Why?

Piper speaks Wyoming (a length-prefixed TCP event protocol). If you just want to
`curl` a sentence and get a `.wav` back, you need an HTTP shim. This repo is that
shim — thin, dependency-light, and stateless.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Check the bridge + upstream Piper are alive |
| `GET` | `/voices` | List available voices (filtered by install state) |
| `POST` | `/tts` | Synthesize `text` → `audio/wav` (streaming) |

### `POST /tts`

```bash
curl -X POST http://localhost:5002/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"xin chào bạn","voice":"vi_VN-vais1000-medium"}' \
  --output hello.wav
```

Request body:

```json
{
  "text": "xin chào bạn",
  "voice": "vi_VN-vais1000-medium"
}
```

- `text` — required, the sentence to speak.
- `voice` — optional. Omit to use the `VOICE` env default. Pass an empty string
  to let Piper pick its default voice.

Response: `audio/wav` (16-bit PCM).

## Quick start

### Docker Compose

```yaml
services:
  piper-tts-bridge:
    build: .
    container_name: piper-tts-bridge
    ports:
      - "5002:5002"
    environment:
      PIPER_HOST: "192.168.100.112"   # host running Piper (Wyoming)
      PIPER_PORT: "10200"
      VOICE: "vi_VN-vais1000-medium"  # optional default voice
    restart: unless-stopped
```

```bash
docker compose up -d --build
curl http://localhost:5002/health   # → {"status":"ok", ...}
```

### Bare Python

```bash
pip install -r requirements.txt
PIPER_HOST=192.168.100.112 PIPER_PORT=10200 python tts_http.py
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PIPER_HOST` | `192.168.100.112` | Piper Wyoming server host |
| `PIPER_PORT` | `10200` | Piper Wyoming server port |
| `VOICE` | `""` | Default voice (e.g. `vi_VN-vais1000-medium`) |
| `API_HOST` | `0.0.0.0` | Bind address for this bridge |
| `API_PORT` | `5002` | Port for this bridge |

## Voice list (Vietnamese)

Piper ships many community voices. `GET /voices` returns the full list; the
Vietnamese subset includes `vi_VN-vais1000-medium`, `vi_VN-vivos-x_low`,
`vi_VN-25hours_single-low`, `banmai`, `minhthu`, `minhquang`, and more.

## How it works

```
client ──HTTP──> tts_http.py ──Wyoming TCP──> piper (Synthesize)
                 │                                    │
                 │<── AudioStart / AudioChunk / AudioStop ──│
                 │  (reassembled into a valid WAV stream)  │
                 └───────── audio/wav ─────────────────────┘
```

The bridge sends a `Synthesize` event to Piper, then streams back the
`AudioStart` (sample rate/width/channels) and `AudioChunk` events, prepending a
minimal RIFF/WAVE header so the result is a playable WAV file.

## License

MIT
