# Piper FastAPI Wrapper — "MIỆNG" (TTS bridge)
# FastAPI HTTP wrapper quanh Piper (Wyoming TCP) để gọi text→audio đơn giản.
# Nối tới Piper đang chạy ở tcp://PIPER_HOST:PIPER_PORT (mặc định 192.168.100.112:10200).
#
# API:
#   GET  /health   → kiểm tra Piper alive
#   GET  /voices   → danh sách voice đã cài
#   POST /tts      → text → audio/wav (streaming)
#
# POST /tts body:
#   {"text": "xin chào", "voice": "vi_VN-vais1000-medium"}
#   - voice: bỏ trống → dùng VOICE env; "" → voice mặc định của Piper.

import logging
import os
import struct
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from wyoming.audio import AudioStart, AudioChunk, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.info import Describe, Info
from wyoming.tts import Synthesize, SynthesizeVoice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("piper-fastapi-wrapper")

PIPER_HOST = os.getenv("PIPER_HOST", "192.168.100.112")
PIPER_PORT = int(os.getenv("PIPER_PORT", "10200"))
VOICE = os.environ.get("VOICE", "")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5002"))

app = FastAPI(
    title="Piper FastAPI Wrapper",
    version="1.0.0",
    description="HTTP bridge over Piper (Wyoming TTS) — text → WAV.",
)


def _wav_header(rate: int, width: int, channels: int) -> bytes:
    bits = width * 8
    bps = rate * channels * bits // 8
    ba = channels * bits // 8
    return struct.pack(
        "<4sL4s4sLHHLLHH4sL",
        b"RIFF", 0xFFFFFFFF, b"WAVE", b"fmt ", 16, 1,
        channels, rate, bps, ba, bits, b"data", 0xFFFFFFFF,
    )


async def _describe(client: AsyncTcpClient) -> Info:
    """Send Describe and read the Info reply."""
    await client.write_event(Describe().event())
    while True:
        ev = await client.read_event()
        if ev is None:
            raise RuntimeError("no info from piper")
        if Info.is_type(ev.type):
            return Info.from_event(ev)


@app.get("/health")
async def health():
    try:
        async with AsyncTcpClient(PIPER_HOST, PIPER_PORT) as client:
            await _describe(client)
        return {
            "status": "ok",
            "piper": f"{PIPER_HOST}:{PIPER_PORT}",
            "voice": VOICE or None,
        }
    except Exception as e:  # noqa: BLE001
        log.error("health check failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/voices")
async def list_voices():
    try:
        async with AsyncTcpClient(PIPER_HOST, PIPER_PORT) as client:
            info = await _describe(client)
        voices = []
        for prog in (info.tts or []):
            if not prog.installed:
                continue
            for v in (prog.voices or []):
                voices.append({
                    "name": v.name,
                    "description": v.description,
                    "languages": v.languages,
                })
        return {
            "voices": sorted(
                voices, key=lambda x: (",".join(x["languages"]), x["name"])
            )
        }
    except Exception as e:  # noqa: BLE001
        log.error("list voices failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None


@app.post("/tts", response_class=StreamingResponse)
async def tts(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="text is empty")

    voice_name = req.voice if req.voice is not None else (VOICE or None)

    async def gen():
        async with AsyncTcpClient(PIPER_HOST, PIPER_PORT) as client:
            synth = Synthesize(
                text=req.text,
                voice=SynthesizeVoice(name=voice_name) if voice_name else None,
            )
            await client.write_event(synth.event())
            header_sent = False
            while True:
                ev = await client.read_event()
                if ev is None:
                    break
                if AudioStart.is_type(ev.type):
                    a = AudioStart.from_event(ev)
                    yield _wav_header(a.rate, a.width, a.channels)
                    header_sent = True
                elif AudioChunk.is_type(ev.type):
                    yield AudioChunk.from_event(ev).audio
                elif AudioStop.is_type(ev.type):
                    break
            if not header_sent:
                log.error("no audio from piper")

    return StreamingResponse(gen(), media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")
