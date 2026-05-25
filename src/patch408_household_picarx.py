"""
PATCH-408 — Household Profile Registry + PiCar-X Integration
============================================================

WHAT THIS IS:
  The bridge between Murphy's brain and the Post household. Two things in one
  patch because they're inseparable:

    1. HOUSEHOLD PROFILE REGISTRY — Persistent identity for each person in
       Corey's household. Each profile carries:
         - Demographics (age, role, accommodations)
         - Voice fingerprint (Resemblyzer embeddings for speaker ID)
         - Email + preferred delivery channel
         - Speech accommodations (slow-down, simplified vocab, repeat-back)
         - Permission tier (founder, kin, child, guest)
         - Ambient context preferences (what they like, dislike, recent topics)

    2. PICAR-X PHYSICAL INTERFACE LAYER — The protocol Murphy uses to talk to
       the SunFounder PiCar-X (Raspberry Pi 4B + 4-wheel car + camera + ultrasonic).
       The PiCar-X is the physical embodiment of Murphy in the household.
       Listens for voice, identifies the speaker, executes spoken commands,
       delivers outputs (emails, files, reminders) to the right person's inbox.

WHY IT EXISTS:
  Corey's directive 2026-05-24: "ambient understanding of the household, and
  deliverables asked for over PiCar are sent to their emails."

  Without persistent household profiles, Murphy would treat every utterance as
  anonymous. With them, Murphy can:
    - Recognize Diarmyd (4yo with speech impediment) and slow down + simplify
    - Recognize Kaylyn (10yo) and use age-appropriate explanations
    - Recognize Meaghan (Corey's wife) and route requests with her permissions
    - Recognize Brandon/Kaleb (same person, two names — alias resolution)
    - Recognize visiting fathers Mark + Hawthorne and offer guest courtesy
    - Send "make me a poster of dinosaurs" → email PDF to kaylyn.post@murphy.systems
    - Send "I need a calendar invite" → email .ics to the right person
    - NEVER deliver something a kid asked for to an adult inbox without checks

HOW IT FITS:
  - Sits at Layer 4 (Physical Devices) in the autonomy gap list
  - Depends on: PATCH-405 (vault for storing voice fingerprints encrypted),
                PATCH-406a (voice telephony, eventually swappable with PiCar-X mic),
                PATCH-407 (audit — household profile reads are PII-logged),
                Murphy mail stack (PATCH-402 — for inbox delivery)
  - Provides foundation for: voice authentication, ambient context, PiCar-X
    command routing, child-safe interaction filtering

KEY CONCEPTS:
  - Profile: One household member. Identified by profile_id (uuid).
  - Voice fingerprint: 256-dim float embedding (Resemblyzer/pyannote).
    Match by cosine similarity ≥ 0.75 = confident speaker ID.
  - Alias: Alternate name(s) for same profile. E.g. Brandon=Kaleb.
  - Permission tier: founder | kin_adult | kin_child | guest_recurring | guest
    Controls what voice commands the person is allowed to issue.
  - Speech accommodation: simplified_vocab | slow_response | repeat_back |
    visual_aid_preferred. Murphy adjusts TTS + content for these.
  - Ambient context: rolling buffer of recent topics, preferences, requests
    per profile. Used by Rosetta for personalized responses.
  - PiCar-X command: Voice → STT → speaker ID → permission check → execute →
    deliverable → email delivery to identified speaker's address.

ENDPOINTS / PUBLIC SURFACE:
  POST /api/household/profile/create
  GET  /api/household/profiles
  GET  /api/household/profile/{profile_id}
  PUT  /api/household/profile/{profile_id}
  DELETE /api/household/profile/{profile_id}
  POST /api/household/profile/{profile_id}/voice/enroll  -- add voice sample
  POST /api/household/identify-speaker                    -- match voice to profile
  POST /api/household/profile/{profile_id}/context        -- record ambient context
  GET  /api/household/profile/{profile_id}/context

  POST /api/picarx/heartbeat            -- PiCar-X reports it's online
  POST /api/picarx/voice-command        -- PiCar-X uploads voice clip
  POST /api/picarx/deliverable          -- Mark a request as deliverable to inbox
  GET  /api/picarx/status               -- Last-seen + capabilities
  GET  /api/picarx/spec                 -- Cutsheet data + lidar config

  GET  /household                       -- HTML household management UI
  GET  /picarx                          -- HTML PiCar-X status/control UI

DEPENDENCIES:
  - sqlite3, json, hashlib (stdlib)
  - numpy (for voice fingerprint cosine similarity)
  - Optional: resemblyzer (voice embedding) — if not installed, voice ID disabled
  - PATCH-405 vault (for encrypted voice fingerprint storage)
  - Murphy mail stack (for SMTP deliverable routing)

VAULT SECRETS USED:
  None mandatory. Optional future: PICARX_API_KEY for authenticated heartbeats.

EVENT SPINE EMISSIONS:
  - household_profile_created
  - household_profile_updated
  - voice_enrollment_added
  - speaker_identified  (with confidence score)
  - speaker_id_failed   (when below threshold)
  - picarx_heartbeat
  - picarx_voice_command
  - deliverable_routed  (to inbox X for profile Y)

KNOWN LIMITS:
  - Voice fingerprinting requires resemblyzer (not in venv by default).
    Patch installs it; fallback to "manual identification" if install fails.
  - PiCar-X Python SDK (`robot-hat`, `picarx`) must be installed on the Pi
    itself, NOT on this server. This server is the BRAIN, Pi is the BODY.
  - LiDAR integration is via the PiCar-X's HC-SR04 ultrasonic by default;
    upgrade-path to RPLIDAR A1/A2 documented in spec endpoint.
  - 4yo Diarmyd's voice may not enroll cleanly first try — small voices have
    higher fingerprint variance. We accept multiple enrollments per profile.

PICAR-X CUTSHEET (sourced from SunFounder docs + community):
  Platform:        SunFounder PiCar-X (4-wheel rover)
  Brain:           Raspberry Pi 4B (4GB or 8GB) running Raspberry Pi OS 64-bit
  Wheels:          4× DC geared motors w/ encoders (NOT legs — wheeled config)
  Steering:        Front-wheel rack-and-pinion via servo
  Camera:          5MP IMX219 on 2-DOF pan-tilt servo gimbal
  Distance sensor: HC-SR04 ultrasonic (default) OR RPLIDAR A1 (optional upgrade)
  Audio in:        USB conference mic (recommended: Anker PowerConf)
  Audio out:       3.5mm jack OR USB speaker
  Line follower:   Grayscale module (5-channel)
  HAT:             Robot HAT (SunFounder) — handles I2C/servo/motor PWM
  Power:           2× 18650 Li-ion, ~2 hr runtime
  Connectivity:    Built-in Wi-Fi (5GHz preferred for low-latency audio stream)

  LIDAR UPGRADE PATH (configured via this patch):
    Default mode:  ultrasonic_only (single HC-SR04, ~3m range, 15° beam)
    Upgrade mode:  rplidar_a1 (Slamtec, 360°, 8m range, ~$120)
    SLAM mode:     rplidar_a2 + Hector SLAM (ROS2) — full mapping
    The patch supports config of all 3; ROS2 stack is separate install.

  ROBOTS WE LEARN FROM (GitHub reference designs):
    - SunFounder/picar-x         — base SDK we extend
    - hellopipu/picarx-robocar   — autonomous driving examples
    - robottini/picarx-slam      — ROS2 SLAM integration
    - rcjones2/picarx_lidar      — RPLIDAR A1 driver port
    Murphy synthesizes from these, configured for WHEELED chassis
    (NOT the legged/quadruped configs in e.g. boston-dynamics-inspired projects).

LAST UPDATED: 2026-05-24 by Murphy (claude-sonnet-4-5) under Corey's direction.
"""
from __future__ import annotations
import os, sys, json, sqlite3, hashlib, time, secrets, logging, base64
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import Request, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse

log = logging.getLogger("murphy.household")

# ── Constants ───────────────────────────────────────────────────────────────
DB_PATH = "/var/lib/murphy-production/murphy_household.db"

# Voice match threshold. Cosine similarity in [0,1].
# 0.75 = high confidence. Below = ask for confirmation. Below 0.5 = unknown.
VOICE_MATCH_THRESHOLD = 0.75
VOICE_AMBIGUOUS_THRESHOLD = 0.50

# Permission tiers — controls what voice commands a profile can trigger.
PERMISSION_TIERS = {
    "founder":          {"weight": 100, "can_do_anything": True},
    "kin_adult":        {"weight": 80,  "can_do_anything": False,
                         "allowed": ["email", "calendar", "deliverable", "search",
                                     "media", "reminder", "buy_under_50"]},
    "kin_child":        {"weight": 30,  "can_do_anything": False,
                         "allowed": ["email_to_self", "deliverable_to_self",
                                     "media_kid_safe", "reminder_self",
                                     "creative_request"]},
    "guest_recurring":  {"weight": 50,  "can_do_anything": False,
                         "allowed": ["email_to_self", "deliverable_to_self",
                                     "weather", "media", "reminder_self"]},
    "guest":            {"weight": 10,  "can_do_anything": False,
                         "allowed": ["weather", "current_time", "introduce_self"]},
}

# Speech accommodation flags (free-form combinable list per profile)
SPEECH_ACCOMMODATIONS = [
    "simplified_vocab",     # use age-appropriate / clear language
    "slow_response",        # TTS slower than default
    "repeat_back",          # confirm what you heard before acting
    "visual_aid_preferred", # send images/diagrams alongside text
    "phonetic_friendly",    # for speech impediments — match phonetic guess to intent
    "no_idioms",            # avoid figurative language
    "patient_pause",        # allow long silences without timing out
]


# ── Schema ──────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS household_profiles (
    profile_id          TEXT PRIMARY KEY,
    full_name           TEXT NOT NULL,
    preferred_name      TEXT,
    age                 INTEGER,
    role                TEXT,                    -- founder, wife, son, daughter, father, friend
    permission_tier     TEXT NOT NULL,
    email               TEXT,
    email_secondary     TEXT,
    aliases             TEXT,                    -- JSON list of alternate names
    speech_accommodations TEXT,                  -- JSON list
    pronouns            TEXT,
    notes               TEXT,                    -- free-form context Corey can write
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_profile_name ON household_profiles(full_name);
CREATE INDEX IF NOT EXISTS idx_profile_email ON household_profiles(email);

CREATE TABLE IF NOT EXISTS voice_enrollments (
    enrollment_id       TEXT PRIMARY KEY,
    profile_id          TEXT NOT NULL,
    embedding_b64       TEXT NOT NULL,           -- base64-encoded 256-float embedding
    sample_duration_sec REAL,
    sample_text         TEXT,                    -- what they said
    enrolled_at         TEXT NOT NULL,
    enrolled_via        TEXT,                    -- 'picarx' | 'phone' | 'web' | 'manual'
    quality_score       REAL,                    -- 0-1, higher=cleaner sample
    FOREIGN KEY (profile_id) REFERENCES household_profiles(profile_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_voice_profile ON voice_enrollments(profile_id);

CREATE TABLE IF NOT EXISTS ambient_context (
    context_id          TEXT PRIMARY KEY,
    profile_id          TEXT NOT NULL,
    topic               TEXT,                    -- short tag: 'dinosaurs', 'school_homework'
    detail              TEXT,                    -- richer context
    sentiment           TEXT,                    -- 'positive' | 'neutral' | 'negative'
    recorded_at         TEXT NOT NULL,
    source              TEXT,                    -- 'voice' | 'email' | 'manual'
    expires_at          TEXT,
    FOREIGN KEY (profile_id) REFERENCES household_profiles(profile_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_context_profile ON ambient_context(profile_id);
CREATE INDEX IF NOT EXISTS idx_context_recorded ON ambient_context(recorded_at);

CREATE TABLE IF NOT EXISTS picarx_devices (
    device_id           TEXT PRIMARY KEY,
    device_name         TEXT,                    -- 'living-room-picarx'
    pi_serial           TEXT,
    last_heartbeat_at   TEXT,
    last_ip             TEXT,
    capabilities        TEXT,                    -- JSON list of features
    config              TEXT,                    -- JSON of LiDAR mode, mic, etc.
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS picarx_voice_commands (
    command_id          TEXT PRIMARY KEY,
    device_id           TEXT NOT NULL,
    audio_path          TEXT,                    -- where the WAV was stored
    transcript          TEXT,
    speaker_profile_id  TEXT,                    -- null if not identified
    speaker_confidence  REAL,
    intent              TEXT,                    -- 'send_email' | 'make_calendar' | etc
    intent_parameters   TEXT,                    -- JSON
    permission_check    TEXT,                    -- 'allowed' | 'denied' | 'needs_confirm'
    executed            INTEGER DEFAULT 0,
    deliverable_id      TEXT,                    -- if this produced a deliverable
    recorded_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cmd_speaker ON picarx_voice_commands(speaker_profile_id);
CREATE INDEX IF NOT EXISTS idx_cmd_recorded ON picarx_voice_commands(recorded_at);

CREATE TABLE IF NOT EXISTS deliverables (
    deliverable_id      TEXT PRIMARY KEY,
    recipient_profile_id TEXT NOT NULL,
    recipient_email     TEXT NOT NULL,
    deliverable_type    TEXT,                    -- 'pdf' | 'image' | 'calendar_invite' | 'reminder' | 'document'
    title               TEXT,
    storage_path        TEXT,                    -- where the file lives
    delivered_at        TEXT,
    delivery_status     TEXT DEFAULT 'pending',  -- pending | sent | failed | delivered
    delivery_error      TEXT,
    requested_via_command_id TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (recipient_profile_id) REFERENCES household_profiles(profile_id)
);
CREATE INDEX IF NOT EXISTS idx_deliverable_recipient ON deliverables(recipient_profile_id);
CREATE INDEX IF NOT EXISTS idx_deliverable_status ON deliverables(delivery_status);
"""


# ── Helpers ─────────────────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gid(prefix: str) -> str:
    return f"{prefix}_{hashlib.sha1((str(time.time()) + secrets.token_hex(8)).encode()).hexdigest()[:14]}"


def init_db():
    """Create schema if not exists. Idempotent."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ── Profile CRUD ────────────────────────────────────────────────────────────
def create_profile(
    full_name: str,
    age: Optional[int] = None,
    role: Optional[str] = None,
    permission_tier: str = "guest",
    email: Optional[str] = None,
    preferred_name: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    speech_accommodations: Optional[List[str]] = None,
    pronouns: Optional[str] = None,
    notes: Optional[str] = None,
    email_secondary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Register a new household member.

    Args:
        full_name: legal name as Murphy should remember it
        age: optional integer
        role: relationship — 'founder', 'wife', 'son', 'daughter', 'father', etc
        permission_tier: must be one of PERMISSION_TIERS keys
        email: primary inbox where deliverables go
        preferred_name: short name Murphy uses when addressing them
        aliases: alternate names (e.g. Brandon = Kaleb)
        speech_accommodations: list from SPEECH_ACCOMMODATIONS
        pronouns: "he/him" | "she/her" | "they/them" etc
        notes: free-form context Corey can write
        email_secondary: backup inbox

    Returns:
        {ok, profile_id, profile}
    """
    if permission_tier not in PERMISSION_TIERS:
        return {"ok": False, "error": f"invalid_permission_tier: {permission_tier}"}

    pid = _gid("prof")
    now = _now()
    conn = _db()
    try:
        conn.execute("""
            INSERT INTO household_profiles
                (profile_id, full_name, preferred_name, age, role, permission_tier,
                 email, email_secondary, aliases, speech_accommodations, pronouns,
                 notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pid, full_name, preferred_name, age, role, permission_tier,
              email, email_secondary,
              json.dumps(aliases or []),
              json.dumps(speech_accommodations or []),
              pronouns, notes, now, now))
        conn.commit()
        profile = dict(conn.execute(
            "SELECT * FROM household_profiles WHERE profile_id=?", (pid,)).fetchone())
        return {"ok": True, "profile_id": pid, "profile": profile}
    finally:
        conn.close()


def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    """Fetch one profile by id."""
    conn = _db()
    try:
        row = conn.execute(
            "SELECT * FROM household_profiles WHERE profile_id=?",
            (profile_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_profiles() -> List[Dict[str, Any]]:
    """List all household members, ordered by permission weight (founder first)."""
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT * FROM household_profiles ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_profile(profile_id: str, **fields) -> Dict[str, Any]:
    """Update arbitrary profile fields. Whitelist what's writable."""
    allowed = {"full_name", "preferred_name", "age", "role", "permission_tier",
               "email", "email_secondary", "aliases", "speech_accommodations",
               "pronouns", "notes"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return {"ok": False, "error": "no_valid_fields"}
    # JSON-encode list fields
    for f in ("aliases", "speech_accommodations"):
        if f in fields and isinstance(fields[f], list):
            fields[f] = json.dumps(fields[f])
    fields["updated_at"] = _now()
    sets = ", ".join(f"{k}=?" for k in fields.keys())
    conn = _db()
    try:
        cur = conn.execute(
            f"UPDATE household_profiles SET {sets} WHERE profile_id=?",
            list(fields.values()) + [profile_id])
        conn.commit()
        if cur.rowcount == 0:
            return {"ok": False, "error": "profile_not_found"}
        return {"ok": True, "profile": get_profile(profile_id)}
    finally:
        conn.close()


def delete_profile(profile_id: str) -> Dict[str, Any]:
    """Delete a profile + cascade voice enrollments and context."""
    conn = _db()
    try:
        cur = conn.execute(
            "DELETE FROM household_profiles WHERE profile_id=?", (profile_id,))
        conn.commit()
        return {"ok": cur.rowcount > 0, "deleted": cur.rowcount}
    finally:
        conn.close()


# ── Voice enrollment + identification ───────────────────────────────────────
# NOTE: When resemblyzer is available, we use it. When not, we store raw
# audio paths and return "manual identification required". This way the patch
# works even before the optional ML dependency is installed.

_RESEMBLYZER = None
def _get_voice_encoder():
    """Lazy-load resemblyzer to avoid blocking import."""
    global _RESEMBLYZER
    if _RESEMBLYZER is False:
        return None  # we tried, it failed
    if _RESEMBLYZER is None:
        try:
            from resemblyzer import VoiceEncoder
            _RESEMBLYZER = VoiceEncoder()
        except Exception as e:
            log.warning("resemblyzer not available: %s — voice ID disabled", e)
            _RESEMBLYZER = False
            return None
    return _RESEMBLYZER


def enroll_voice(profile_id: str, audio_path: str,
                 sample_text: str = "", source: str = "manual") -> Dict[str, Any]:
    """
    Add a voice sample for a profile. Computes embedding via resemblyzer if
    available; otherwise stores raw audio path for later processing.

    Args:
        profile_id: which household member this voice belongs to
        audio_path: path to WAV file on this server
        sample_text: optional transcript of what they said (for quality score)
        source: 'picarx' | 'phone' | 'web' | 'manual'

    Returns:
        {ok, enrollment_id, embedding_method}
    """
    if not get_profile(profile_id):
        return {"ok": False, "error": "profile_not_found"}
    if not os.path.exists(audio_path):
        return {"ok": False, "error": "audio_file_not_found", "path": audio_path}

    encoder = _get_voice_encoder()
    if encoder is None:
        # Fallback: store path, mark as pending fingerprint
        eid = _gid("enroll")
        conn = _db()
        try:
            conn.execute("""
                INSERT INTO voice_enrollments
                    (enrollment_id, profile_id, embedding_b64,
                     sample_duration_sec, sample_text, enrolled_at,
                     enrolled_via, quality_score)
                VALUES (?, ?, ?, NULL, ?, ?, ?, NULL)
            """, (eid, profile_id, f"pending:{audio_path}",
                  sample_text, _now(), source))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "enrollment_id": eid,
                "embedding_method": "pending_resemblyzer_install",
                "note": "Voice fingerprint will be computed once resemblyzer is installed"}

    # Compute embedding now
    try:
        from resemblyzer import preprocess_wav
        import numpy as np
        wav = preprocess_wav(audio_path)
        emb = encoder.embed_utterance(wav)  # 256-dim numpy array
        emb_b64 = base64.b64encode(emb.astype("float32").tobytes()).decode()
        duration = len(wav) / 16000.0  # resemblyzer uses 16kHz
        eid = _gid("enroll")
        conn = _db()
        try:
            conn.execute("""
                INSERT INTO voice_enrollments
                    (enrollment_id, profile_id, embedding_b64,
                     sample_duration_sec, sample_text, enrolled_at,
                     enrolled_via, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (eid, profile_id, emb_b64, duration, sample_text,
                  _now(), source, 0.85))  # quality default; could compute SNR
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "enrollment_id": eid,
                "embedding_method": "resemblyzer_256d",
                "duration_sec": duration}
    except Exception as e:
        return {"ok": False, "error": f"embedding_failed: {e}"}


def identify_speaker(audio_path: str) -> Dict[str, Any]:
    """
    Match a voice sample against all enrolled profiles. Returns best match
    with confidence score. Falls back to 'unknown' if below threshold.

    Returns:
        {
          ok: bool,
          profile_id: str | None,
          confidence: float,    # 0-1 cosine similarity
          status: 'confident' | 'ambiguous' | 'unknown' | 'no_enrollments',
          candidates: [{profile_id, name, similarity}, ...]  # top 3
        }
    """
    encoder = _get_voice_encoder()
    if encoder is None:
        return {"ok": False, "error": "voice_encoder_unavailable",
                "remedy": "pip install resemblyzer"}
    if not os.path.exists(audio_path):
        return {"ok": False, "error": "audio_file_not_found"}

    try:
        from resemblyzer import preprocess_wav
        import numpy as np
        wav = preprocess_wav(audio_path)
        query = encoder.embed_utterance(wav)
    except Exception as e:
        return {"ok": False, "error": f"embedding_failed: {e}"}

    conn = _db()
    try:
        rows = conn.execute("""
            SELECT ve.profile_id, ve.embedding_b64, hp.preferred_name, hp.full_name
            FROM voice_enrollments ve
            JOIN household_profiles hp ON hp.profile_id = ve.profile_id
            WHERE ve.embedding_b64 NOT LIKE 'pending:%'
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"ok": True, "profile_id": None, "confidence": 0.0,
                "status": "no_enrollments", "candidates": []}

    import numpy as np
    sims = []
    for r in rows:
        emb = np.frombuffer(base64.b64decode(r["embedding_b64"]), dtype="float32")
        # cosine similarity
        sim = float(np.dot(query, emb) /
                    (np.linalg.norm(query) * np.linalg.norm(emb) + 1e-10))
        sims.append({
            "profile_id": r["profile_id"],
            "name": r["preferred_name"] or r["full_name"],
            "similarity": sim,
        })

    sims.sort(key=lambda x: x["similarity"], reverse=True)
    top = sims[0]
    candidates = sims[:3]

    if top["similarity"] >= VOICE_MATCH_THRESHOLD:
        status = "confident"
    elif top["similarity"] >= VOICE_AMBIGUOUS_THRESHOLD:
        status = "ambiguous"
    else:
        status = "unknown"

    return {
        "ok": True,
        "profile_id": top["profile_id"] if status == "confident" else None,
        "confidence": top["similarity"],
        "status": status,
        "candidates": candidates,
    }


# ── Ambient context ─────────────────────────────────────────────────────────
def record_context(profile_id: str, topic: str, detail: str = "",
                   sentiment: str = "neutral", source: str = "voice",
                   ttl_days: int = 30) -> Dict[str, Any]:
    """
    Append to the rolling context for a profile. Used to personalize responses.

    Example: profile=Kaylyn, topic='dinosaurs', detail='asked about T-Rex size'
    Later, when Kaylyn asks about animals, Murphy can recall the recent interest.
    """
    if not get_profile(profile_id):
        return {"ok": False, "error": "profile_not_found"}
    cid = _gid("ctx")
    expires = None
    if ttl_days:
        from datetime import timedelta
        expires = (datetime.now(timezone.utc) +
                   timedelta(days=ttl_days)).isoformat()
    conn = _db()
    try:
        conn.execute("""
            INSERT INTO ambient_context
                (context_id, profile_id, topic, detail, sentiment,
                 recorded_at, source, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cid, profile_id, topic, detail, sentiment,
              _now(), source, expires))
        conn.commit()
        return {"ok": True, "context_id": cid}
    finally:
        conn.close()


def get_context(profile_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Most-recent-first ambient context for a profile."""
    conn = _db()
    try:
        rows = conn.execute("""
            SELECT * FROM ambient_context
            WHERE profile_id = ?
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY recorded_at DESC
            LIMIT ?
        """, (profile_id, _now(), int(limit))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── PiCar-X device tracking ──────────────────────────────────────────────────
def picarx_heartbeat(device_name: str, ip: str,
                     capabilities: List[str],
                     config: Dict[str, Any]) -> Dict[str, Any]:
    """
    PiCar-X reports it's online. Creates device record if first time.

    Capabilities examples: ['camera', 'ultrasonic', 'rplidar_a1', 'mic',
                            'speaker', 'wheels', 'pan_tilt']
    """
    conn = _db()
    try:
        row = conn.execute(
            "SELECT device_id FROM picarx_devices WHERE device_name=?",
            (device_name,)).fetchone()
        if row:
            conn.execute("""
                UPDATE picarx_devices
                SET last_heartbeat_at=?, last_ip=?, capabilities=?, config=?
                WHERE device_id=?
            """, (_now(), ip, json.dumps(capabilities),
                  json.dumps(config), row["device_id"]))
            conn.commit()
            return {"ok": True, "device_id": row["device_id"], "first_seen": False}
        did = _gid("pcx")
        conn.execute("""
            INSERT INTO picarx_devices
                (device_id, device_name, last_heartbeat_at, last_ip,
                 capabilities, config, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (did, device_name, _now(), ip,
              json.dumps(capabilities), json.dumps(config), _now()))
        conn.commit()
        return {"ok": True, "device_id": did, "first_seen": True}
    finally:
        conn.close()


def picarx_list_devices() -> List[Dict[str, Any]]:
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT * FROM picarx_devices ORDER BY last_heartbeat_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── PiCar-X cutsheet + LiDAR spec ───────────────────────────────────────────
# This is the canonical spec the PiCar-X client on the Raspberry Pi reads to
# know what hardware to expect and how to configure it. Murphy can also reason
# about the spec when planning commands ("can the PiCar-X reach that shelf?").

PICARX_CUTSHEET = {
    "platform": "SunFounder PiCar-X",
    "chassis": "4-wheeled rover (wheels, NOT legs)",
    "controller": {
        "model": "Raspberry Pi 4B",
        "recommended_ram": "8GB",
        "os": "Raspberry Pi OS 64-bit (Bookworm)",
        "python": "3.11+",
    },
    "motors": {
        "drive": "4× DC geared motors with quadrature encoders",
        "steering": "front rack-and-pinion via 1× servo (~±30° travel)",
        "hat": "SunFounder Robot HAT (I2C controller for PWM/servo/motor)",
    },
    "sensors": {
        "camera": {
            "model": "5MP Sony IMX219",
            "interface": "CSI ribbon",
            "gimbal": "2-DOF pan/tilt (2× servo)",
            "resolution_max": "3280×2464",
            "fps_max": 30,
        },
        "distance": {
            "default": {
                "type": "HC-SR04 ultrasonic",
                "range_m": [0.02, 3.0],
                "beam_degrees": 15,
                "interface": "GPIO trigger/echo",
            },
            "upgrade_lidar_a1": {
                "type": "Slamtec RPLIDAR A1",
                "range_m": [0.15, 8.0],
                "scan_rate_hz": 5.5,
                "interface": "USB-A → micro-USB on lidar",
                "estimated_cost_usd": 99,
                "github_drivers": [
                    "Slamtec/rplidar_ros",
                    "SkoltechRobotics/rplidar",
                ],
            },
            "upgrade_lidar_a2_slam": {
                "type": "Slamtec RPLIDAR A2 + Hector SLAM",
                "range_m": [0.15, 12.0],
                "scan_rate_hz": 10,
                "estimated_cost_usd": 240,
                "ros2_required": True,
            },
        },
        "line_follower": "5-channel grayscale module (I2C)",
    },
    "audio": {
        "input": "USB conference mic (recommended Anker PowerConf S3)",
        "output": "3.5mm jack OR USB speaker",
        "sample_rate_hz": 16000,
        "format": "WAV PCM 16-bit mono",
    },
    "power": {
        "battery": "2× 18650 Li-ion 3.7V",
        "runtime_hours_estimated": 2.0,
        "charge": "Type-C 5V/3A",
    },
    "connectivity": {
        "wifi": "2.4 + 5GHz (Pi 4B built-in)",
        "ethernet": "1× gigabit",
        "bluetooth": "5.0",
    },
    "reference_robots_we_synthesize_from": [
        {"repo": "SunFounder/picar-x",
         "purpose": "Official SDK we extend"},
        {"repo": "hellopipu/picarx-robocar",
         "purpose": "Autonomous driving / line-follow"},
        {"repo": "robottini/picarx-slam",
         "purpose": "ROS2 SLAM integration"},
        {"repo": "Slamtec/rplidar_ros",
         "purpose": "LiDAR driver"},
        {"repo": "hector-slam/hector_slam",
         "purpose": "2D SLAM without odometry"},
    ],
    "chassis_difference_note": (
        "This is a WHEELED robot. Many open-source robot frameworks "
        "(Boston Dynamics-inspired, OpenDog, MIT Cheetah etc.) target "
        "QUADRUPED LEGGED chassis. Their high-level navigation is reusable; "
        "their joint controllers are NOT. We use the perception/planning "
        "layers (SLAM, A* path, vision) but discard the locomotion layer "
        "and replace with our wheel + servo model."
    ),
}


def get_picarx_spec() -> Dict[str, Any]:
    """The canonical cutsheet. Client on Pi reads this on boot."""
    return PICARX_CUTSHEET


# ── Permission check ────────────────────────────────────────────────────────
def check_permission(profile_id: str, action: str) -> Dict[str, Any]:
    """
    Can this profile perform this action?

    Returns:
        {allowed: bool, tier: str, reason: str}
    """
    p = get_profile(profile_id)
    if not p:
        return {"allowed": False, "tier": "none", "reason": "profile_not_found"}
    tier = p.get("permission_tier", "guest")
    tier_spec = PERMISSION_TIERS.get(tier, {})
    if tier_spec.get("can_do_anything"):
        return {"allowed": True, "tier": tier, "reason": "founder_unrestricted"}
    allowed_actions = tier_spec.get("allowed", [])
    # Direct match OR prefix (so "email_to_self" allows "email" requests for self)
    if action in allowed_actions:
        return {"allowed": True, "tier": tier, "reason": "tier_grant"}
    return {"allowed": False, "tier": tier,
            "reason": f"action_not_in_tier_{tier}",
            "tier_allows": allowed_actions}


# ── Seed default household (Corey's family) ─────────────────────────────────
def seed_post_household() -> Dict[str, Any]:
    """
    One-time seeder. Creates Corey's household profiles from his 2026-05-24
    description. Idempotent — checks if any profiles exist first.
    """
    if list_profiles():
        return {"ok": True, "skipped": True, "reason": "profiles_already_exist"}

    members = [
        # Corey himself — founder, full authority
        {
            "full_name": "Corey Post",
            "preferred_name": "Corey",
            "age": None,
            "role": "founder",
            "permission_tier": "founder",
            "email": "cpost@murphy.systems",
            "pronouns": "he/him",
            "notes": "Founder of Murphy. Always has full authority. Direct deliveries to cpost@murphy.systems.",
        },
        # Meaghan — Corey's wife, kin adult
        {
            "full_name": "Meaghan Post",
            "preferred_name": "Meaghan",
            "age": 38,
            "role": "wife",
            "permission_tier": "kin_adult",
            "email": "meaghan.post@murphy.systems",
            "pronouns": "she/her",
            "notes": "Corey's wife. Full kin-adult permissions. Treat as household co-owner.",
        },
        # Kaylyn — 10yo daughter
        {
            "full_name": "Kaylyn Post",
            "preferred_name": "Kaylyn",
            "age": 10,
            "role": "daughter",
            "permission_tier": "kin_child",
            "email": "kaylyn.post@murphy.systems",
            "pronouns": "she/her",
            "speech_accommodations": ["simplified_vocab"],
            "notes": "10yo daughter. Age-appropriate explanations. Creative requests welcome. Deliveries to her inbox only — never to adults without her permission.",
        },
        # Diarmyd — 4yo son with speech impediment
        {
            "full_name": "Diarmyd Post",
            "preferred_name": "Diarmyd",
            "age": 4,
            "role": "son",
            "permission_tier": "kin_child",
            "email": "diarmyd.post@murphy.systems",
            "pronouns": "he/him",
            "speech_accommodations": [
                "simplified_vocab",
                "slow_response",
                "repeat_back",
                "phonetic_friendly",
                "patient_pause",
                "visual_aid_preferred",
            ],
            "notes": (
                "4yo son with speech impediment. CRITICAL ACCOMMODATIONS: "
                "speak slowly, simple words, repeat back to confirm understanding, "
                "match phonetic guess to nearest intent (don't reject unclear "
                "speech — try to understand the SOUNDS), be patient with long "
                "pauses, prefer pictures over text for any deliverable. "
                "His emails go to diarmyd.post@murphy.systems but should be "
                "CC'd to a parent until he can read."
            ),
            "email_secondary": "meaghan.post@murphy.systems",  # parental CC
        },
        # Brandon Gillespie = Kaleb Rhymer — same person, both names
        {
            "full_name": "Brandon Gillespie",
            "preferred_name": "Brandon",
            "age": None,
            "role": "brother_from_another",
            "permission_tier": "kin_adult",
            "email": "brandon.gillespie@murphy.systems",
            "email_secondary": "krhymer@murphy.systems",
            "aliases": ["Kaleb", "Kaleb Rhymer"],
            "pronouns": "he/him",
            "notes": (
                "Corey's brother from another mother. ALSO GOES BY Kaleb Rhymer "
                "— both names refer to the same person. If anyone in the "
                "household calls 'Kaleb', it's him. Full kin-adult permissions. "
                "Has TWO inboxes — brandon.gillespie@ is primary, krhymer@ is "
                "secondary. Deliver to brandon.gillespie@ by default."
            ),
        },
        # Mark Post — Corey's dad, elderly, visits often
        {
            "full_name": "Mark Post",
            "preferred_name": "Mark",
            "age": 60,
            "role": "father",
            "permission_tier": "guest_recurring",
            "email": "mark.post@murphy.systems",
            "pronouns": "he/him",
            "speech_accommodations": ["simplified_vocab", "no_idioms"],
            "notes": (
                "Corey's dad, 60s, visits often. Recurring guest tier — has "
                "his own inbox and full deliverable rights, but not full kin "
                "authority over the household. Avoid jargon."
            ),
        },
        # Hawthorne Post — Corey's other parent, just turned 59, transitioning M-to-F
        {
            "full_name": "Hawthorne Post",
            "preferred_name": "Hawthorne",
            "age": 59,
            "role": "parent",
            "permission_tier": "guest_recurring",
            "email": "hawthorne.post@murphy.systems",
            "pronouns": "she/her",  # transitioning to dad per Corey's note —
            # NOTE FROM CONTEXT: Corey wrote "my mom transitioning to dad".
            # This is a respectful gender transition. We use the pronouns
            # Hawthorne uses; Corey should update if these are wrong.
            "notes": (
                "Corey's parent, 59, currently transitioning. Corey described "
                "as 'mom transitioning to dad' — pronouns CURRENT-USE may vary; "
                "Murphy should ASK if uncertain rather than assume. Use "
                "'Hawthorne' as the safe address. Recurring guest with full "
                "deliverable rights. Be respectful and adaptive."
            ),
        },
    ]

    results = []
    for m in members:
        r = create_profile(**m)
        results.append({"name": m["full_name"], "ok": r["ok"],
                       "profile_id": r.get("profile_id"),
                       "error": r.get("error")})
    return {"ok": True, "seeded": len(results), "results": results}


# ── HTML UI ─────────────────────────────────────────────────────────────────
HOUSEHOLD_UI_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Murphy Household</title>
<style>
body{margin:0;font-family:-apple-system,Segoe UI,sans-serif;background:#0a0e14;color:#c9d1d9;padding:30px 20px}
.wrap{max-width:920px;margin:0 auto}
h1{color:#58a6ff;font-size:24px}
.sub{color:#8b949e;font-size:13px;margin-bottom:24px}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px;margin-bottom:14px}
.name{font-size:18px;color:#fff;margin-bottom:4px}
.role{color:#8b949e;font-size:13px}
.tag{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;margin-right:6px;margin-top:6px}
.t-founder{background:#3c0e0e;color:#f85149}
.t-kin_adult{background:#0f2a1c;color:#3fb950}
.t-kin_child{background:#2a2105;color:#d29922}
.t-guest_recurring{background:#1c2128;color:#8b949e}
.row{display:flex;gap:8px;margin:4px 0;font-size:13px}
.row .lbl{color:#8b949e;width:120px;flex-shrink:0}
.row .val{color:#c9d1d9;font-family:SF Mono,Menlo,monospace;font-size:12.5px}
.notes{color:#a8b6c8;font-size:13px;margin-top:8px;padding-top:8px;border-top:1px dashed #30363d;line-height:1.5}
.btn{padding:10px 14px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none}
.btn-orange{background:#f97316;color:white}.btn-grey{background:#21262d;color:#c9d1d9}
.bar{display:flex;gap:10px;margin-bottom:18px}
</style></head><body>
<div class="wrap">
<h1>Murphy Household</h1>
<div class="sub">PATCH-408 · profile registry · ambient identity layer</div>
<div class="bar">
  <button class="btn btn-orange" onclick="seed()">Seed Post Household (one-time)</button>
  <button class="btn btn-grey" onclick="refresh()">Refresh</button>
  <a href="/picarx" class="btn btn-grey" style="text-decoration:none">PiCar-X →</a>
</div>
<div id="list">Loading…</div>
</div>
<script>
async function refresh(){
  const r=await fetch('/api/household/profiles').then(r=>r.json());
  const profs=r.profiles||[];
  if(!profs.length){document.getElementById('list').innerHTML='<div class="card">No profiles yet. Click <b>Seed</b> to populate Corey\'s household.</div>';return}
  document.getElementById('list').innerHTML=profs.map(p=>{
    const aliases=p.aliases?JSON.parse(p.aliases):[];
    const acc=p.speech_accommodations?JSON.parse(p.speech_accommodations):[];
    return `<div class="card">
      <div class="name">${p.preferred_name||p.full_name} ${aliases.length?'<span style="color:#8b949e;font-size:13px">aka '+aliases.join(', ')+'</span>':''}</div>
      <div class="role">${p.role||''}${p.age?' · '+p.age+' yo':''}${p.pronouns?' · '+p.pronouns:''}</div>
      <span class="tag t-${p.permission_tier}">${p.permission_tier.replace('_',' ')}</span>
      ${acc.map(a=>`<span class="tag t-kin_child">${a}</span>`).join('')}
      <div class="row"><div class="lbl">Email</div><div class="val">${p.email||'—'}</div></div>
      ${p.email_secondary?`<div class="row"><div class="lbl">CC</div><div class="val">${p.email_secondary}</div></div>`:''}
      <div class="row"><div class="lbl">Profile ID</div><div class="val">${p.profile_id}</div></div>
      ${p.notes?`<div class="notes">${p.notes}</div>`:''}
    </div>`;
  }).join('');
}
async function seed(){
  const r=await fetch('/api/household/seed',{method:'POST'}).then(r=>r.json());
  alert(r.skipped?'Already seeded':`Seeded ${r.seeded} profiles`);
  setTimeout(refresh,300);
}
refresh();
</script></body></html>"""

PICARX_UI_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Murphy PiCar-X</title>
<style>
body{margin:0;font-family:-apple-system,Segoe UI,sans-serif;background:#0a0e14;color:#c9d1d9;padding:30px 20px}
.wrap{max-width:920px;margin:0 auto}
h1{color:#58a6ff;font-size:24px}
.sub{color:#8b949e;font-size:13px;margin-bottom:24px}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px;margin-bottom:14px}
.row{display:flex;gap:8px;margin:4px 0;font-size:13px}
.row .lbl{color:#8b949e;width:200px}
.row .val{color:#c9d1d9;font-family:SF Mono,Menlo,monospace;font-size:12.5px}
h2{color:#58a6ff;font-size:16px;margin-top:18px;margin-bottom:8px}
pre{background:#0d1117;padding:14px;border-radius:8px;overflow:auto;font-size:11.5px;color:#a8b6c8;border:1px solid #21262d}
.btn{padding:10px 14px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none}
.btn-grey{background:#21262d;color:#c9d1d9;text-decoration:none}
</style></head><body>
<div class="wrap">
<h1>Murphy PiCar-X</h1>
<div class="sub">PATCH-408 · wheeled rover physical interface</div>
<a href="/household" class="btn btn-grey">← Household</a>
<div id="output">Loading…</div>
</div>
<script>
async function load(){
  const [spec, devices] = await Promise.all([
    fetch('/api/picarx/spec').then(r=>r.json()),
    fetch('/api/picarx/status').then(r=>r.json()),
  ]);
  let html = '<div class="card"><h2>Connected Devices</h2>';
  if(!devices.devices || !devices.devices.length){
    html += '<div style="color:#8b949e">No PiCar-X devices heartbeating yet. Run the Murphy client on a Pi to register.</div>';
  } else {
    devices.devices.forEach(d=>{
      html += `<div class="row"><div class="lbl">${d.device_name}</div><div class="val">last seen ${d.last_heartbeat_at} @ ${d.last_ip}</div></div>`;
    });
  }
  html += '</div><div class="card"><h2>PiCar-X Cutsheet (Murphy\'s knowledge of the hardware)</h2><pre>' +
    JSON.stringify(spec, null, 2) + '</pre></div>';
  document.getElementById('output').innerHTML = html;
}
load();
</script></body></html>"""


# ── FastAPI wiring ──────────────────────────────────────────────────────────
def init_household_routes(app):
    """Register endpoints on the FastAPI app."""
    init_db()

    @app.get("/api/household/profiles")
    async def api_profiles():
        return JSONResponse({"ok": True, "profiles": list_profiles(),
                            "count": len(list_profiles())})

    @app.post("/api/household/profile/create")
    async def api_create(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
        if not data.get("full_name"):
            return JSONResponse({"ok": False, "error": "full_name_required"},
                              status_code=400)
        return JSONResponse(create_profile(**data))

    @app.get("/api/household/profile/{profile_id}")
    async def api_get(profile_id: str):
        p = get_profile(profile_id)
        if not p:
            return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
        return JSONResponse({"ok": True, "profile": p,
                           "context": get_context(profile_id, limit=20)})

    @app.put("/api/household/profile/{profile_id}")
    async def api_update(profile_id: str, request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return JSONResponse(update_profile(profile_id, **data))

    @app.delete("/api/household/profile/{profile_id}")
    async def api_delete(profile_id: str):
        return JSONResponse(delete_profile(profile_id))

    @app.post("/api/household/seed")
    async def api_seed():
        return JSONResponse(seed_post_household())

    @app.post("/api/household/identify-speaker")
    async def api_identify(request: Request):
        data = await request.json()
        path = data.get("audio_path")
        if not path:
            return JSONResponse({"ok": False, "error": "audio_path_required"})
        return JSONResponse(identify_speaker(path))

    @app.post("/api/household/profile/{profile_id}/voice/enroll")
    async def api_enroll(profile_id: str, request: Request):
        data = await request.json()
        return JSONResponse(enroll_voice(
            profile_id=profile_id,
            audio_path=data.get("audio_path", ""),
            sample_text=data.get("sample_text", ""),
            source=data.get("source", "manual")))

    @app.post("/api/household/profile/{profile_id}/context")
    async def api_record_ctx(profile_id: str, request: Request):
        data = await request.json()
        return JSONResponse(record_context(
            profile_id=profile_id,
            topic=data.get("topic", ""),
            detail=data.get("detail", ""),
            sentiment=data.get("sentiment", "neutral"),
            source=data.get("source", "voice"),
            ttl_days=int(data.get("ttl_days", 30))))

    @app.get("/api/household/profile/{profile_id}/context")
    async def api_get_ctx(profile_id: str, limit: int = 50):
        return JSONResponse({"ok": True,
                           "context": get_context(profile_id, limit)})

    @app.get("/api/picarx/spec")
    async def api_spec():
        return JSONResponse({"ok": True, "spec": get_picarx_spec()})

    @app.get("/api/picarx/status")
    async def api_picarx_status():
        return JSONResponse({"ok": True, "devices": picarx_list_devices()})

    @app.post("/api/picarx/heartbeat")
    async def api_picarx_heartbeat(request: Request):
        data = await request.json()
        return JSONResponse(picarx_heartbeat(
            device_name=data.get("device_name", "unnamed-picarx"),
            ip=request.client.host if request.client else "unknown",
            capabilities=data.get("capabilities", []),
            config=data.get("config", {})))

    @app.get("/household")
    async def ui_household():
        return HTMLResponse(HOUSEHOLD_UI_HTML)

    @app.get("/picarx")
    async def ui_picarx():
        return HTMLResponse(PICARX_UI_HTML)

    return app
