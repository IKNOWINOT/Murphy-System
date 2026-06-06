"""
voice_bridge.py — Real-time voice loop for Twilio Media Streams.

Pipeline:
  Caller speaks
    → Twilio sends 8kHz μ-law base64 frames over WebSocket
    → decode μ-law → 16-bit PCM 8kHz
    → buffer until VAD detects end of utterance (~700ms silence)
    → upsample 8kHz → 16kHz
    → Whisper tiny.en transcribes
    → send transcript to murphy_voice.reply_in_voice (same unified voice as /chat)
    → Piper synthesizes Murphy's reply as 22050Hz WAV
    → downsample 22050 → 8kHz
    → encode PCM → μ-law
    → base64 + send back over WebSocket in 20ms frames
    → caller hears Murphy speak
"""
from __future__ import annotations
import asyncio, audioop, base64, io, json, logging, os, sqlite3, time, wave, subprocess
from typing import Optional
import numpy as np

log = logging.getLogger("murphy.voice_bridge")

PIPER_BIN = "/opt/piper/piper"  # binary stays at /opt/piper for libs; voices live in voice_assets
PIPER_MODEL = "/opt/Murphy-System/voice_assets/piper/en_US-lessac-medium.onnx"
VOICE_DB = "/var/lib/murphy-production/murphy_voice.db"

# Lazy-load Whisper (75 MB model) on first use
_WHISPER = None
def _whisper():
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        _WHISPER = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        log.info("voice_bridge: Whisper tiny.en loaded")
    return _WHISPER


# ──────────────────────────────────────────────────────────────────────────
# Voice Activity Detection — simple energy-based, good enough for phone audio
# ──────────────────────────────────────────────────────────────────────────
class VAD:
    """
    Tracks PCM frames and signals when an utterance has ended.
    Phone audio is 8kHz mono 16-bit signed PCM.
    """
    SILENCE_THRESHOLD = 500   # RMS amplitude below this = silence
    SILENCE_DURATION  = 0.7   # seconds of silence to trigger end-of-utterance
    MIN_UTTERANCE     = 0.4   # ignore utterances shorter than this

    def __init__(self):
        self.buffer = bytearray()
        self.silence_started_at: Optional[float] = None
        self.speech_started_at: Optional[float] = None

    def feed(self, pcm_chunk: bytes) -> Optional[bytes]:
        """Feed PCM. Returns full utterance bytes when one completes, else None."""
        self.buffer.extend(pcm_chunk)
        now = time.monotonic()

        rms = audioop.rms(pcm_chunk, 2)  # 2 bytes per sample
        if rms > self.SILENCE_THRESHOLD:
            self.silence_started_at = None
            if self.speech_started_at is None:
                self.speech_started_at = now
        else:
            if self.silence_started_at is None:
                self.silence_started_at = now
            elif (now - self.silence_started_at) >= self.SILENCE_DURATION:
                # End of utterance
                if self.speech_started_at and (now - self.speech_started_at) >= self.MIN_UTTERANCE:
                    utterance = bytes(self.buffer)
                    self.buffer.clear()
                    self.silence_started_at = None
                    self.speech_started_at = None
                    return utterance
                # Too short — discard noise
                self.buffer.clear()
                self.speech_started_at = None
                self.silence_started_at = None
        return None


# ──────────────────────────────────────────────────────────────────────────
# STT — 8kHz PCM bytes → text via Whisper
# ──────────────────────────────────────────────────────────────────────────
def transcribe(pcm_8khz: bytes) -> str:
    if not pcm_8khz:
        return ""
    # Upsample 8kHz → 16kHz (Whisper expects 16kHz)
    pcm_16khz, _ = audioop.ratecv(pcm_8khz, 2, 1, 8000, 16000, None)
    audio_np = np.frombuffer(pcm_16khz, dtype=np.int16).astype(np.float32) / 32768.0
    segments, _ = _whisper().transcribe(audio_np, language="en", vad_filter=True)
    text = " ".join(seg.text for seg in segments).strip()
    return text


# ──────────────────────────────────────────────────────────────────────────
# TTS — text → 8kHz μ-law base64 frames (20ms each)
# ──────────────────────────────────────────────────────────────────────────
def synthesize_mulaw_frames(text: str) -> list[str]:
    """Returns list of base64-encoded 20ms μ-law frames ready for Twilio."""
    if not text:
        return []

    # Piper: write text to stdin, get WAV on stdout
    p = subprocess.run(
        [PIPER_BIN, "--model", PIPER_MODEL, "--output_raw"],
        input=text.encode(),
        capture_output=True,
        timeout=15,
    )
    if p.returncode != 0:
        log.error("piper failed: %s", p.stderr.decode()[:300])
        return []

    raw_pcm = p.stdout  # 22050Hz mono 16-bit PCM
    # Downsample 22050 → 8000 Hz
    pcm_8khz, _ = audioop.ratecv(raw_pcm, 2, 1, 22050, 8000, None)
    # PCM → μ-law (1 byte per sample)
    mulaw = audioop.lin2ulaw(pcm_8khz, 2)

    # 20ms frames @ 8kHz = 160 samples = 160 bytes
    frames = []
    for i in range(0, len(mulaw), 160):
        chunk = mulaw[i:i+160]
        if len(chunk) < 160:
            chunk = chunk + b'\xff' * (160 - len(chunk))  # μ-law silence pad
        frames.append(base64.b64encode(chunk).decode())
    return frames


# ──────────────────────────────────────────────────────────────────────────
# Voice loop — orchestrates one call
# ──────────────────────────────────────────────────────────────────────────
async def run_voice_loop(ws, call_id: str):
    """
    Owns the WebSocket lifecycle for one Twilio Media Stream call.
    `ws` is a FastAPI WebSocket already accepted.
    """
    from starlette.websockets import WebSocketDisconnect

    vad = VAD()
    stream_sid: Optional[str] = None
    chunks_recv = 0
    chunks_sent = 0
    history: list[dict] = []

    def _log_event(event_type, detail=None):
        try:
            conn = sqlite3.connect(VOICE_DB, timeout=2)
            conn.execute(
                "INSERT INTO voice_events (call_id, event_type, detail, created_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                (call_id, event_type, json.dumps(detail or {})),
            )
            conn.commit(); conn.close()
        except Exception as e:
            log.debug("voice_event log failed: %s", e)

    async def speak(text: str):
        nonlocal chunks_sent
        if not stream_sid:
            return
        log.info("voice_bridge[%s]: speaking %r", call_id, text[:80])
        _log_event("murphy_speaks", {"text": text[:200]})
        frames = synthesize_mulaw_frames(text)
        for frame_b64 in frames:
            await ws.send_text(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": frame_b64},
            }))
            chunks_sent += 1
            await asyncio.sleep(0.02)  # 20 ms pace

    async def handle_utterance(pcm: bytes):
        text = transcribe(pcm)
        if not text or len(text) < 2:
            return
        log.info("voice_bridge[%s]: heard %r", call_id, text[:120])
        _log_event("caller_said", {"text": text[:300]})
        history.append({"u": text, "t": time.time()})

        # Run Murphy voice in a thread (it does HTTP to LLM, can take a few sec)
        try:
            from src.murphy_voice import reply_in_voice
            from src.self_audit import snapshot
            loop = asyncio.get_event_loop()
            reply = await loop.run_in_executor(
                None,
                lambda: reply_in_voice(
                    text,
                    audit=snapshot(),
                    history=[{"u": h["u"], "m": h.get("m","")} for h in history[-6:]],
                    channel="voice",
                ),
            )
        except Exception as e:
            log.exception("reply_in_voice failed")
            reply = "Sorry Corey, I hit an error. Try again."

        history[-1]["m"] = reply
        await speak(reply)

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            event = data.get("event")

            if event == "start":
                start = data.get("start", {})
                stream_sid = start.get("streamSid")
                _log_event("stream_started", {"stream_sid": stream_sid})
                log.info("voice_bridge[%s]: stream %s", call_id, stream_sid)
                # Greet immediately
                await asyncio.sleep(0.3)
                await speak("Hey Corey, Murphy here. Talk to me.")

            elif event == "media":
                chunks_recv += 1
                mulaw_b64 = data["media"]["payload"]
                mulaw_bytes = base64.b64decode(mulaw_b64)
                pcm = audioop.ulaw2lin(mulaw_bytes, 2)
                utterance = vad.feed(pcm)
                if utterance:
                    # Spawn handler so we keep reading audio
                    asyncio.create_task(handle_utterance(utterance))

            elif event == "stop":
                _log_event("stream_stopped",
                          {"chunks_recv": chunks_recv, "chunks_sent": chunks_sent})
                break

    except WebSocketDisconnect:
        _log_event("stream_disconnect",
                  {"chunks_recv": chunks_recv, "chunks_sent": chunks_sent})
    except Exception as e:
        log.exception("voice_bridge[%s] error", call_id)
        _log_event("stream_error", {"error": str(e)[:300]})

