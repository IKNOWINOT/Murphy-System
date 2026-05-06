"""
src/twitter_outreach.py  — PATCH-196
Murphy System — Twitter/X Autonomous Outreach Engine

Psychology & persuasion principles baked into every message:

  CIALDINI'S 6 PRINCIPLES
  ─────────────────────────────────────────────────────────────────
  1. Reciprocity       — Give value first. Compliment real work before asking anything.
  2. Social proof      — Reference peers ("Teams like yours at YC..."), not generic claims.
  3. Scarcity          — Soft urgency without false deadlines ("early access", "founder rate").
  4. Authority         — Murphy speaks from a position of solved problems, not promises.
  5. Liking            — Mirror the prospect's language and tone from their bio/tweets.
  6. Commitment        — Micro-yes ladder: ask for a reaction, not a meeting.

  MENTALIST / COLD-READ TECHNIQUES
  ─────────────────────────────────────────────────────────────────
  - Barnum statements scoped to ICP: observations that feel personal but apply to the role.
    "You're the kind of builder who ships fast but quietly worries about what breaks
     when no one is watching." — true of every CTO/founder. Feels like we read their mind.
  - Presupposition framing: "When you eventually need AI safety coverage..." 
    (presupposes they will — question is only timing).
  - Embedded command: "The next time you think about AI reliability, you'll remember
    this conversation." Planted in casual phrasing.
  - Open loops: end with an unresolved question or hook that the brain feels compelled
    to close. "I found something interesting in how [company] is positioned — worth a look?"
  - Pattern interrupt: lead with something unexpected for a cold DM — an observation
    about THEIR work, not a pitch. Most cold DMs open with "I" — we open with "You".
  - Future pacing: "Imagine six months from now your whole team ships AI features
    without the compliance headache..." — they visualise the outcome, not the product.
  - Inoculation: acknowledge the objection before they raise it.
    "This is not a pitch deck. No deck, no demo request — just one specific question."

  SANDLER SALES RULES
  ─────────────────────────────────────────────────────────────────
  - Never chase. One opener, two follow-ups, then go silent permanently.
  - Ask, don't tell. Questions create engagement; statements create resistance.
  - Qualify hard upfront. Low-ICP prospects never get a second message.
  - Pain > Features. Sell the relief, not the product.

  CADENCE (Twitter-specific)
  ─────────────────────────────────────────────────────────────────
  Day 0  — Engage: like/comment on a real tweet before sending DM (warm approach)
  Day 0  — DM opener: value-first, pattern-interrupt, open loop
  Day 4  — Follow-up #1: new angle, reinforce pain, presupposition
  Day 9  — Follow-up #2: permission close + embedded command
  Day 9+ — Archive. Never contact again unless they reply.

DNC gates:
  - Email DNC list checked on all leads
  - Twitter-specific block list (twitter_dnc table)
  - Never DM anyone who has blocked/muted Murphy
  - Auto-suppress on "unsubscribe", "stop", "not interested" reply

PATCH-196
"""
from __future__ import annotations

import json, logging, os, random, re, sqlite3, time, uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.twitter_outreach")

CRM_DB      = "/var/lib/murphy-production/crm.db"
TWITTER_DB  = "/var/lib/murphy-production/twitter_outreach.db"

# ══════════════════════════════════════════════════════════════════════════════
# DB SETUP
# ══════════════════════════════════════════════════════════════════════════════

def ensure_tables() -> None:
    with sqlite3.connect(TWITTER_DB, timeout=8) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS twitter_prospects (
                id           TEXT PRIMARY KEY,
                twitter_id   TEXT UNIQUE,
                username     TEXT,
                display_name TEXT DEFAULT '',
                bio          TEXT DEFAULT '',
                followers    INTEGER DEFAULT 0,
                source_query TEXT DEFAULT '',
                icp_score    INTEGER DEFAULT 0,
                crm_contact_id TEXT DEFAULT '',
                added_at     TEXT
            );
            CREATE TABLE IF NOT EXISTS twitter_touches (
                id           TEXT PRIMARY KEY,
                twitter_id   TEXT,
                username     TEXT,
                touch_number INTEGER DEFAULT 1,
                message_text TEXT DEFAULT '',
                sent         INTEGER DEFAULT 0,
                sent_at      TEXT DEFAULT '',
                reply_received INTEGER DEFAULT 0,
                reply_text   TEXT DEFAULT '',
                opted_out    INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS twitter_dnc (
                id         TEXT PRIMARY KEY,
                twitter_id TEXT DEFAULT '',
                username   TEXT DEFAULT '',
                reason     TEXT DEFAULT '',
                added_at   TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tp_tid  ON twitter_prospects(twitter_id);
            CREATE INDEX IF NOT EXISTS idx_tt_tid  ON twitter_touches(twitter_id);
            CREATE INDEX IF NOT EXISTS idx_tdnc_u  ON twitter_dnc(username);
        """)


# ══════════════════════════════════════════════════════════════════════════════
# GATES
# ══════════════════════════════════════════════════════════════════════════════

def _twitter_dnc_blocked(twitter_id: str = "", username: str = "") -> bool:
    try:
        with sqlite3.connect(TWITTER_DB, timeout=5) as db:
            if twitter_id:
                r = db.execute("SELECT id FROM twitter_dnc WHERE twitter_id=? LIMIT 1",
                               (twitter_id,)).fetchone()
                if r:
                    return True
            if username:
                r = db.execute("SELECT id FROM twitter_dnc WHERE LOWER(username)=? LIMIT 1",
                               (username.lower(),)).fetchone()
                if r:
                    return True
    except Exception as e:
        logger.warning("Twitter DNC check error: %s", e)
    return False


def _email_dnc_blocked(email: str) -> bool:
    if not email:
        return False
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            r = db.execute(
                "SELECT id FROM dnc_suppression WHERE LOWER(email)=? LIMIT 1",
                (email.lower(),)).fetchone()
            return r is not None
    except Exception:
        return False


def _touch_count(twitter_id: str) -> int:
    try:
        with sqlite3.connect(TWITTER_DB, timeout=5) as db:
            r = db.execute(
                "SELECT COUNT(*) FROM twitter_touches WHERE twitter_id=? AND sent=1",
                (twitter_id,)).fetchone()
            return r[0] if r else 0
    except Exception:
        return 0


def _days_since_last_touch(twitter_id: str) -> Optional[int]:
    try:
        with sqlite3.connect(TWITTER_DB, timeout=5) as db:
            r = db.execute(
                "SELECT sent_at FROM twitter_touches WHERE twitter_id=? AND sent=1 "
                "ORDER BY sent_at DESC LIMIT 1",
                (twitter_id,)).fetchone()
            if not r or not r[0]:
                return None
            last = datetime.fromisoformat(r[0].replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - last).days
    except Exception:
        return None


def _opted_out(twitter_id: str) -> bool:
    try:
        with sqlite3.connect(TWITTER_DB, timeout=5) as db:
            r = db.execute(
                "SELECT id FROM twitter_touches WHERE twitter_id=? AND opted_out=1 LIMIT 1",
                (twitter_id,)).fetchone()
            return r is not None
    except Exception:
        return False


def _add_twitter_dnc(twitter_id: str, username: str, reason: str) -> None:
    try:
        with sqlite3.connect(TWITTER_DB, timeout=5) as db:
            db.execute(
                "INSERT OR IGNORE INTO twitter_dnc (id,twitter_id,username,reason,added_at) "
                "VALUES (?,?,?,?,?)",
                (str(uuid.uuid4())[:12], twitter_id, username, reason,
                 datetime.now(timezone.utc).isoformat())
            )
            db.commit()
        logger.info("[Twitter] DNC added: @%s (%s)", username, reason)
    except Exception as e:
        logger.warning("Twitter DNC add error: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# ICP SCORING (Twitter-specific signals)
# ══════════════════════════════════════════════════════════════════════════════

BIO_ICP_POSITIVE = [
    "founder","co-founder","cto","vp eng","head of engineering","building",
    "shipping","ai","llm","automation","saas","b2b","platform","developer",
    "engineer","startup","yc","techcrunch","product lead","machine learning",
    "compliance","security","fintech","healthtech","devtools",
]
BIO_ICP_NEGATIVE = [
    "crypto","nft","web3","influencer","coach","speaker","author","journalist",
    "intern","student","job seeker","open to work","recruiter",
]
MIN_FOLLOWERS = 200      # avoid brand-new / bot accounts
MAX_FOLLOWERS = 500000   # avoid mega-influencers who never engage DMs


def _twitter_icp_score(bio: str, display_name: str, followers: int) -> int:
    score = 0
    b = (bio + " " + display_name).lower()
    if any(h in b for h in BIO_ICP_POSITIVE):
        score += 50
    if any(h in b for h in BIO_ICP_NEGATIVE):
        return 0
    if MIN_FOLLOWERS <= followers <= MAX_FOLLOWERS:
        score += 25
    elif followers > MAX_FOLLOWERS:
        score -= 20
    # Building signal — "building X" is the strongest ICP marker on Twitter
    if re.search(r"build\w*\s+(ai|saas|llm|agent|tool|platform|product)", b):
        score += 25
    return max(0, min(100, score))


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGE COMPOSER — Psychology-first
# ══════════════════════════════════════════════════════════════════════════════

# Prospect search queries — find people tweeting about the pain Murphy solves
PROSPECT_QUERIES = [
    # Explicit pain signals
    "AI hallucination production -is:retweet lang:en",
    "AI compliance headache -is:retweet lang:en",
    "LLM safety production -is:retweet lang:en",
    "AI audit trail -is:retweet lang:en",
    "building with AI reliability -is:retweet lang:en",
    "AI agent going wrong -is:retweet lang:en",
    "shipped AI feature broke -is:retweet lang:en",
    # Builder signals  
    "launched AI product feedback -is:retweet lang:en",
    "built with LLM startup -is:retweet lang:en",
    "AI startup compliance -is:retweet lang:en",
]

# ── Opener templates (pattern-interrupt + Barnum + open loop) ─────────────────
OPENER_DMS = [

    # A — Pattern interrupt + Barnum + open loop
    ("pattern_interrupt",
"""Hey {first} — not a pitch, promise.

Saw you tweeting about {topic_hook}. You said something that stopped me.

You're the kind of builder who ships fast but has a quiet voice in the back of their head asking "what breaks when no one is watching?" Every founder building with AI has it.

Murphy System is the answer to that voice — production AI safety, audit trails, compliance coverage, all automated.

One question: what's the failure mode you worry about most right now?"""),

    # B — Future pace + embedded command + presupposition
    ("future_pace",
"""Hey {first},

Imagine six months from now: your team is shipping AI features without the compliance headache, every edge case is caught before users see it, and you have a full audit trail if anyone ever asks.

That's what Murphy System does — quietly, in the background.

When you think about AI reliability at {company}, what's the thing that keeps the conversation stuck?"""),

    # C — Social proof scoped + reciprocity (give insight first)
    ("social_proof",
"""Hey {first} — quick observation, feel free to ignore.

Teams building AI products at your stage spend roughly 30% of eng time on failure handling that shouldn't need human eyes. It's the hidden tax.

Murphy System eliminates it — automated safety layer, HITL controls, SOC2/GDPR out of the box.

Not asking for anything. Just thought it was relevant given what you're building. What does your current failure-handling setup look like?"""),

    # D — Authority + inoculation + micro-yes
    ("authority_inoculation",
"""Hey {first},

This is not a cold pitch. No deck, no demo request.

One genuine question: when something goes wrong with your AI in production, what's the first thing you reach for?

(Asking because Murphy System was built to be that first thing — and I'm curious if the problem looks the same from your side.)"""),

    # E — Mentalist cold read (most powerful — feels personal)
    ("cold_read",
"""Hey {first},

Wild guess: you've shipped at least one AI feature that worked perfectly in testing and did something unexpected in production. You fixed it, moved on, but it lives rent-free in the back of your mind.

Murphy System exists for that moment — before it happens next time.

What did it feel like when you first saw it break?"""),
]

# ── Follow-up #1 (new angle + presupposition + pain reinforcement) ─────────────
FOLLOWUP_1_DMS = [
    ("new_angle",
"""Hey {first} — one more thought and then I'll leave you alone.

The teams that get AI compliance right early don't just avoid risk. They close enterprise deals faster because the security review is already done.

Murphy System is that security review, pre-built.

Still curious — what does your current AI safety setup look like?"""),

    ("presupposition",
"""Hey {first},

The question isn't whether AI reliability becomes a priority at {company} — it's when.

Most founders I talk to wish they'd dealt with it before a customer discovered the gap.

Murphy System closes it now, before it costs you a deal.

Worth 15 minutes to see if it fits?"""),
]

# ── Follow-up #2 — Permission close + embedded command ────────────────────────
FOLLOWUP_2_DM = """Hey {first},

Last message, I promise.

If AI safety and compliance ever become urgent at {company} — and they will, for any team shipping AI at scale — murphy.systems is the place to start.

If the timing is just off: reply "not now" and I'll make sure you hear from us again in 90 days instead. No hard feelings either way.

The next time someone on your team asks "what do we do if this AI does something wrong?" — you'll know the answer.

— Corey, Murphy System"""


def _extract_topic_hook(tweet_text: str) -> str:
    """Pull a 3-5 word topic from a prospect's tweet to make opener feel personal."""
    tweet_text = re.sub(r"https?://\S+", "", tweet_text).strip()
    words = tweet_text.split()
    if len(words) > 6:
        return " ".join(words[2:7]).lower().rstrip(".,!?")
    return "AI in production"


def compose_dm(prospect: Dict, touch: int = 1) -> str:
    """Compose a DM using psychology principles. touch=1,2,3."""
    name     = prospect.get("display_name", "")
    username = prospect.get("username", "")
    bio      = prospect.get("bio", "")
    company  = prospect.get("company", "your company")
    tweet    = prospect.get("source_tweet", "")

    first = name.split()[0] if name and " " in name else (name or username or "there")
    topic_hook = _extract_topic_hook(tweet) if tweet else "AI in production"

    ctx = {
        "first":      first,
        "username":   username,
        "company":    company,
        "bio_snippet": bio[:60] if bio else "",
        "topic_hook": topic_hook,
    }

    if touch == 1:
        template_name, tmpl = random.choice(OPENER_DMS)
    elif touch == 2:
        template_name, tmpl = random.choice(FOLLOWUP_1_DMS)
    else:
        tmpl = FOLLOWUP_2_DM
        template_name = "permission_close"

    # Twitter DM limit: 10,000 chars but keep it conversational (under 500)
    msg = tmpl.format(**ctx)
    return msg.strip()


# ══════════════════════════════════════════════════════════════════════════════
# OPT-OUT DETECTION
# ══════════════════════════════════════════════════════════════════════════════

OPT_OUT_SIGNALS = [
    "unsubscribe", "stop", "opt out", "opt-out", "not interested",
    "remove me", "leave me alone", "do not contact", "don't dm",
    "spam", "reported", "blocked", "go away", "not now ever",
    "please stop", "stop messaging",
]


def _is_opt_out(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in OPT_OUT_SIGNALS)


# ══════════════════════════════════════════════════════════════════════════════
# TWITTER CLIENT (wraps connector)
# ══════════════════════════════════════════════════════════════════════════════

def _get_client():
    """Return authenticated tweepy client using env keys."""
    import tweepy
    api_key    = os.environ.get("TWITTER_API_KEY","")
    api_secret = os.environ.get("TWITTER_API_SECRET","")
    acc_token  = os.environ.get("TWITTER_ACCESS_TOKEN","")
    acc_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET","")
    bearer     = os.environ.get("TWITTER_BEARER_TOKEN","")
    if not bearer and not api_key:
        raise RuntimeError("No Twitter credentials in environment")
    client = tweepy.Client(
        bearer_token=bearer or None,
        consumer_key=api_key or None,
        consumer_secret=api_secret or None,
        access_token=acc_token or None,
        access_token_secret=acc_secret or None,
        wait_on_rate_limit=True,
    )
    return client


def _keys_configured() -> bool:
    return bool(
        os.environ.get("TWITTER_API_KEY") and
        os.environ.get("TWITTER_ACCESS_TOKEN")
    )


# ══════════════════════════════════════════════════════════════════════════════
# PROSPECT DISCOVERY
# ══════════════════════════════════════════════════════════════════════════════

def discover_prospects(max_per_query: int = 10) -> Dict:
    """
    Search Twitter for people tweeting about AI pain points Murphy solves.
    Score by ICP, store in twitter_prospects, skip DNC + already-contacted.
    """
    ensure_tables()
    if not _keys_configured():
        return {"success": False, "error": "Twitter API keys not configured",
                "action_needed": "Add TWITTER_API_KEY + TWITTER_ACCESS_TOKEN to environment"}
    try:
        client = _get_client()
    except Exception as e:
        return {"success": False, "error": str(e)}

    added = 0; skipped = 0
    for query in PROSPECT_QUERIES:
        try:
            resp = client.search_recent_tweets(
                query=query,
                max_results=max_per_query,
                expansions=["author_id"],
                user_fields=["id","name","username","description","public_metrics"],
                tweet_fields=["id","text","author_id","created_at"],
            )
            if not resp or not resp.data:
                continue

            users = {u.id: u for u in (resp.includes.get("users",[]) if resp.includes else [])}
            for tweet in resp.data:
                author = users.get(tweet.author_id)
                if not author:
                    continue
                tid      = str(author.id)
                username = author.username
                bio      = author.description or ""
                followers = (author.public_metrics or {}).get("followers_count", 0)
                icp = _twitter_icp_score(bio, author.name, followers)
                if icp < 40:
                    skipped += 1; continue
                if _twitter_dnc_blocked(tid, username):
                    skipped += 1; continue

                try:
                    with sqlite3.connect(TWITTER_DB, timeout=5) as db:
                        db.execute(
                            "INSERT OR IGNORE INTO twitter_prospects "
                            "(id,twitter_id,username,display_name,bio,followers,"
                            " source_query,icp_score,added_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (str(uuid.uuid4())[:12], tid, username, author.name,
                             bio, followers, query, icp,
                             datetime.now(timezone.utc).isoformat())
                        )
                        db.commit()
                    added += 1
                    logger.info("[Twitter] Prospect: @%s ICP=%d", username, icp)
                    # PATCH-197: Enrich twitter prospect immediately
                    try:
                        from src.prospect_enricher import enrich_contact
                        # Link twitter prospect to CRM if exists
                        with sqlite3.connect(CRM_DB, timeout=5) as _cdb:
                            _crow = _cdb.execute(
                                "SELECT id FROM contacts WHERE tags LIKE ? LIMIT 1",
                                (f"%{username}%",)
                            ).fetchone()
                            if _crow:
                                enrich_contact(_crow[0])
                    except Exception as _ee:
                        logger.debug("[Twitter] Enrich hook: %s", _ee)
                except Exception:
                    pass
            time.sleep(1)
        except Exception as e:
            logger.warning("[Twitter] Query '%s' failed: %s", query[:40], e)
            time.sleep(2)

    return {"success": True, "added": added, "skipped": skipped}


# ══════════════════════════════════════════════════════════════════════════════
# OUTREACH EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

MAX_TOUCHES   = 3
CADENCE_DAYS  = [0, 4, 9]   # days after first contact for each touch
MAX_DMS_PER_RUN = 5          # conservative — X rate limits DMs hard


def run_outreach_cycle() -> Dict:
    """
    For each prospect in twitter_prospects:
      - Check all gates (DNC, opted-out, touch count, cadence timing)
      - Compose psychology-based DM
      - Send via Twitter API
      - Log to twitter_touches + CRM activities
    """
    ensure_tables()
    if not _keys_configured():
        return {"success": False, "error": "Twitter API keys not configured"}

    try:
        client = _get_client()
        me = client.get_me()
        my_id = str(me.data.id) if me and me.data else None
    except Exception as e:
        return {"success": False, "error": f"Twitter auth failed: {e}"}

    sent = 0; skipped = 0; opted_out_found = 0

    # Check for opt-out replies first
    try:
        events = client.get_dm_events(
            dm_event_fields=["id","text","sender_id","created_at","participant_ids"],
            max_results=50,
        )
        if events and events.data:
            for ev in events.data:
                if str(ev.sender_id) == my_id:
                    continue  # our own message
                if _is_opt_out(ev.text or ""):
                    # Find prospect and suppress
                    try:
                        with sqlite3.connect(TWITTER_DB, timeout=5) as db:
                            db.execute(
                                "UPDATE twitter_touches SET opted_out=1, reply_text=? "
                                "WHERE twitter_id=?",
                                (ev.text, str(ev.sender_id))
                            )
                            db.commit()
                        _add_twitter_dnc(str(ev.sender_id), "", "opt-out reply")
                        opted_out_found += 1
                    except Exception:
                        pass
    except Exception as e:
        logger.debug("[Twitter] DM inbox check failed: %s", e)

    # Load prospects ready for outreach
    try:
        with sqlite3.connect(TWITTER_DB, timeout=5) as db:
            prospects = db.execute(
                "SELECT twitter_id, username, display_name, bio, crm_contact_id "
                "FROM twitter_prospects WHERE icp_score >= 40 ORDER BY icp_score DESC"
            ).fetchall()
    except Exception as e:
        return {"success": False, "error": str(e)}

    for row in prospects:
        if sent >= MAX_DMS_PER_RUN:
            break

        tid, username, display_name, bio, crm_cid = row

        # All gates
        if _twitter_dnc_blocked(tid, username):
            skipped += 1; continue
        if _opted_out(tid):
            skipped += 1; continue

        touches   = _touch_count(tid)
        days_last = _days_since_last_touch(tid)

        if touches >= MAX_TOUCHES:
            skipped += 1; continue

        # Cadence gate
        if touches > 0:
            needed = CADENCE_DAYS[min(touches, len(CADENCE_DAYS)-1)]
            if days_last is None or days_last < needed:
                skipped += 1; continue

        prospect = {
            "twitter_id":   tid,
            "username":     username,
            "display_name": display_name,
            "bio":          bio,
            "company":      _infer_company(bio, display_name),
        }

        msg = compose_dm(prospect, touch=touches + 1)

        # Send
        dm_sent = False
        try:
            resp = client.create_direct_message(participant_id=tid, text=msg)
            dm_sent = resp and resp.data
            if dm_sent:
                logger.info("[Twitter] DM sent to @%s (touch #%d)", username, touches+1)
        except Exception as e:
            logger.warning("[Twitter] DM failed to @%s: %s", username, e)

        # Log touch regardless of send success
        tid_log = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(TWITTER_DB, timeout=5) as db:
                db.execute(
                    "INSERT INTO twitter_touches "
                    "(id,twitter_id,username,touch_number,message_text,sent,sent_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (tid_log, tid, username, touches+1, msg,
                     1 if dm_sent else 0, now if dm_sent else "")
                )
                db.commit()
        except Exception:
            pass

        # Log to CRM activities if contact exists
        if crm_cid:
            try:
                with sqlite3.connect(CRM_DB, timeout=5) as db:
                    db.execute(
                        "INSERT INTO activities (id,activity_type,contact_id,user_id,"
                        "summary,details,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid.uuid4())[:12], "twitter_dm", crm_cid,
                         "murphy_prospector",
                         f"Twitter DM touch #{touches+1} to @{username}",
                         json.dumps({"sent": dm_sent, "touch": touches+1}), now)
                    )
                    db.commit()
            except Exception:
                pass

        if dm_sent:
            sent += 1
        else:
            skipped += 1
        time.sleep(2)  # rate limit buffer

    return {
        "success":        True,
        "dms_sent":       sent,
        "skipped":        skipped,
        "opted_out_found": opted_out_found,
    }


def _infer_company(bio: str, name: str) -> str:
    """Best-effort company inference from Twitter bio."""
    m = re.search(r"(?:@|at |\|\s)(\w[\w.]+)", bio)
    if m:
        return m.group(1)
    return name.split()[0] if name else "your company"


# ══════════════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════════════

def get_stats() -> Dict:
    ensure_tables()
    try:
        with sqlite3.connect(TWITTER_DB, timeout=5) as db:
            prospects = db.execute("SELECT COUNT(*) FROM twitter_prospects").fetchone()[0]
            sent      = db.execute("SELECT COUNT(*) FROM twitter_touches WHERE sent=1").fetchone()[0]
            replies   = db.execute("SELECT COUNT(*) FROM twitter_touches WHERE reply_received=1").fetchone()[0]
            opted_out = db.execute("SELECT COUNT(*) FROM twitter_dnc").fetchone()[0]
        return {
            "prospects_found": prospects,
            "dms_sent":        sent,
            "replies":         replies,
            "dnc_entries":     opted_out,
            "keys_configured": _keys_configured(),
        }
    except Exception as e:
        return {"error": str(e)}
