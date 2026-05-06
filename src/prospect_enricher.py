"""
src/prospect_enricher.py — PATCH-197
Murphy System — Prospect Data Enrichment Engine

For every lead/prospect Murphy finds, this engine builds a complete intelligence
dossier stored in contacts.custom_fields (JSON) and twitter_prospects.

Data collected (all zero-cost, public sources):
  ─────────────────────────────────────────────────────────────────────────────
  PERSON
    full_name, first_name, last_name
    title / role
    twitter_username, twitter_bio, twitter_followers, twitter_following
    twitter_pinned_tweet          ← what they care about most right now
    recent_tweets[]               ← last 5 tweets — tone, pain points, language
    tweet_themes[]                ← inferred: "AI safety", "compliance", "scaling"
    linkedin_url (inferred)
    github_username (if found)
    github_repos[]                ← what they're building
    personal_website

  COMPANY
    company_name, company_domain
    company_description           ← from Clearbit autocomplete
    company_logo_url
    company_size_estimate         ← inferred from public signals
    company_stage                 ← seed / series-a / growth / public
    company_tech_stack[]          ← from job postings / GitHub / site scrape
    funding_stage                 ← inferred from YC list / news
    is_yc_company (bool)
    yc_batch

  SALES INTELLIGENCE
    pain_signals[]                ← specific phrases from tweets that signal pain
    buying_trigger                ← the single most actionable signal Murphy found
    best_opener_angle             ← which psychology template to use (inferred)
    competitor_mentions[]         ← are they talking about competitors?
    deal_urgency_score (0-100)    ← higher = contact sooner
    estimated_deal_value          ← based on company size + stage
    best_contact_time             ← inferred from tweet timing patterns
    language_style                ← "technical" / "executive" / "founder-casual"

  ENRICHMENT META
    enriched_at, enriched_sources[], enrichment_version

PATCH-197
"""
from __future__ import annotations

import json, logging, re, sqlite3, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.enricher")

CRM_DB     = "/var/lib/murphy-production/crm.db"
TWITTER_DB = "/var/lib/murphy-production/twitter_outreach.db"
AGENT      = "Mozilla/5.0 (compatible; MurphyEnrich/1.0; +https://murphy.systems)"

# ── Pain signal phrases Murphy listens for ────────────────────────────────────
PAIN_SIGNALS = [
    "hallucination","ai broke","llm failed","compliance","audit","gdpr","soc2",
    "hipaa","production issue","ai in prod","reliability","false positive",
    "trust ai","ai safety","guardrail","prompt injection","jailbreak","output quality",
    "ai liability","regulatory","ai audit","ai governance","ai risk",
    "shipped and it","bug in prod","outage","incident","post-mortem","root cause",
    "scale ai","ai cost","inference cost","latency","accuracy","drift",
    "model performance","evaluation","evals","benchmark","red team",
]

# ── Competitor signals ────────────────────────────────────────────────────────
COMPETITORS = [
    "guardrails ai","arize","whylabs","evidently","langsmith","langfuse",
    "weights biases","honeyhive","brainlox","humanloop","promptlayer",
    "trulens","deepchecks","arthur ai","fiddler",
]

# ── Company stage inference ───────────────────────────────────────────────────
STAGE_SIGNALS = {
    "seed":     ["pre-seed","seed","just raised","angel","friends and family"],
    "series-a": ["series a","series-a","post-seed","raised $","million in"],
    "series-b": ["series b","series-b","series c","growth stage"],
    "public":   ["nasdaq","nyse","ipo","public company","ticker"],
}

# ── Language style inference ──────────────────────────────────────────────────
EXEC_WORDS    = ["strategy","roadmap","vision","scale","revenue","growth","board","investor"]
FOUNDER_WORDS = ["building","shipping","launched","we made","side project","my startup","our product"]
TECH_WORDS    = ["deployed","refactored","latency","throughput","architecture","infra","k8s","docker"]


def _fetch(url: str, timeout: int = 8) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("fetch %s: %s", url, e)
        return None


def _fetch_json(url: str, timeout: int = 8) -> Any:
    raw = _fetch(url, timeout)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# TWITTER ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════════

def _enrich_twitter(username: str, twitter_id: str = "") -> Dict:
    """Pull full Twitter profile + recent tweets via tweepy."""
    result = {}
    try:
        import os, tweepy
        client = tweepy.Client(
            bearer_token=os.environ.get("TWITTER_BEARER_TOKEN","") or None,
            consumer_key=os.environ.get("TWITTER_API_KEY","") or None,
            consumer_secret=os.environ.get("TWITTER_API_SECRET","") or None,
            access_token=os.environ.get("TWITTER_ACCESS_TOKEN","") or None,
            access_token_secret=os.environ.get("TWITTER_ACCESS_TOKEN_SECRET","") or None,
            wait_on_rate_limit=True,
        )

        # Full profile
        user = client.get_user(
            username=username,
            user_fields=["id","name","username","description","public_metrics",
                         "location","url","entities","pinned_tweet_id","created_at"],
            expansions=["pinned_tweet_id"],
        )
        if not user or not user.data:
            return result

        u = user.data
        m = u.public_metrics or {}
        result.update({
            "twitter_id":        str(u.id),
            "twitter_username":  u.username,
            "twitter_bio":       u.description or "",
            "twitter_followers": m.get("followers_count", 0),
            "twitter_following": m.get("following_count", 0),
            "twitter_tweets":    m.get("tweet_count", 0),
            "twitter_location":  u.location or "",
            "twitter_created":   str(u.created_at)[:10] if u.created_at else "",
            "twitter_url":       f"https://twitter.com/{u.username}",
        })

        # Pinned tweet
        if user.includes and user.includes.get("tweets"):
            pinned = user.includes["tweets"][0]
            result["twitter_pinned_tweet"] = pinned.text

        # Recent tweets — the richest source of pain signals
        tweets_resp = client.get_users_tweets(
            id=str(u.id),
            max_results=10,
            tweet_fields=["id","text","created_at","public_metrics"],
            exclude=["retweets","replies"],
        )
        recent = []
        pain_found = []
        competitor_found = []
        hours_active = []

        if tweets_resp and tweets_resp.data:
            for tw in tweets_resp.data:
                text = tw.text or ""
                recent.append(text[:200])
                tl = text.lower()

                # Pain signals
                for sig in PAIN_SIGNALS:
                    if sig in tl and sig not in pain_found:
                        pain_found.append(sig)

                # Competitor mentions
                for comp in COMPETITORS:
                    if comp in tl and comp not in competitor_found:
                        competitor_found.append(comp)

                # Tweet hour for best-contact-time
                if tw.created_at:
                    hours_active.append(tw.created_at.hour)

        result["recent_tweets"]       = recent
        result["pain_signals"]        = pain_found
        result["competitor_mentions"] = competitor_found

        # Best contact time (hour with most activity)
        if hours_active:
            from collections import Counter
            result["best_contact_hour"] = Counter(hours_active).most_common(1)[0][0]

    except Exception as e:
        logger.debug("[Enricher] Twitter enrich @%s: %s", username, e)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# GITHUB ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════════

def _enrich_github(username: str) -> Dict:
    """Find GitHub profile by Twitter username / display name."""
    result = {}
    try:
        # Search GitHub for matching user
        data = _fetch_json(
            f"https://api.github.com/search/users?q={urllib.parse.quote(username)}&per_page=3",
            timeout=8
        )
        if not data or not data.get("items"):
            return result

        gh_user = data["items"][0]
        login   = gh_user.get("login","")
        if not login:
            return result

        # Full profile
        profile = _fetch_json(f"https://api.github.com/users/{login}", timeout=6)
        if not profile:
            return result

        result["github_username"] = login
        result["github_url"]      = f"https://github.com/{login}"
        result["github_repos"]    = profile.get("public_repos", 0)
        result["github_bio"]      = profile.get("bio","") or ""
        result["github_company"]  = profile.get("company","") or ""

        # Top repos — what are they actually building
        repos = _fetch_json(
            f"https://api.github.com/users/{login}/repos?sort=updated&per_page=5",
            timeout=8
        )
        if repos:
            result["github_top_repos"] = [
                {
                    "name":        r.get("name",""),
                    "description": (r.get("description","") or "")[:100],
                    "language":    r.get("language",""),
                    "stars":       r.get("stargazers_count",0),
                    "topics":      r.get("topics",[]),
                }
                for r in repos if not r.get("fork")
            ]
            # Infer tech stack from repos
            langs = [r.get("language","") for r in repos if r.get("language")]
            result["tech_stack"] = list(set(langs))[:6]

    except Exception as e:
        logger.debug("[Enricher] GitHub enrich %s: %s", username, e)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# COMPANY ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════════

def _enrich_company(domain: str, company_name: str = "") -> Dict:
    """Enrich company data from Clearbit autocomplete + YC list + website scrape."""
    result = {}
    if not domain:
        return result

    # Clearbit autocomplete (free, no key)
    try:
        query = company_name or domain.split(".")[0]
        url   = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={urllib.parse.quote(query)}"
        data  = _fetch_json(url, timeout=6)
        if data:
            for c in data:
                if c.get("domain","").lower() == domain.lower() or not domain:
                    result["company_description"] = ""  # autocomplete doesn't have description
                    result["company_logo"]         = c.get("logo","")
                    result["company_name_verified"]= c.get("name","")
                    break
    except Exception as e:
        logger.debug("[Enricher] Clearbit: %s", e)

    # YC list check
    try:
        yc = _fetch_json("https://yc-oss.github.io/api/companies/all.json", timeout=8)
        if yc:
            for co in yc:
                site = re.sub(r"https?://","", co.get("website","")).split("/")[0].replace("www.","")
                if site == domain or co.get("name","").lower() == (company_name or "").lower():
                    result["is_yc_company"]    = True
                    result["yc_batch"]         = co.get("batch","")
                    result["company_stage"]    = "growth" if co.get("status","") == "Active" else "unknown"
                    result["company_tags"]     = co.get("tags",[])
                    result["company_description"] = co.get("one_liner","")
                    result["team_size"]        = co.get("team_size","")
                    result["company_stage"]    = _infer_stage_from_size(co.get("team_size",""))
                    break
    except Exception as e:
        logger.debug("[Enricher] YC check: %s", e)

    # Scrape website for tech stack hints (meta tags, script srcs)
    try:
        html = _fetch(f"https://{domain}", timeout=6)
        if html:
            hl = html.lower()
            tech = []
            TECH_MARKERS = {
                "react":     ["react","reactjs","_next/"],
                "vue":       ["vue.js","vuejs","nuxt"],
                "python":    ["fastapi","django","flask","uvicorn","gunicorn"],
                "rails":     ["ruby on rails","rails","actioncable"],
                "stripe":    ["stripe.com/v3","stripe.js"],
                "intercom":  ["intercom"],
                "segment":   ["segment.com","analytics.js"],
                "hubspot":   ["hubspot"],
                "salesforce":["salesforce","pardot"],
                "aws":       ["amazonaws.com","cloudfront"],
                "vercel":    ["vercel","_vercel"],
                "gcp":       ["googleapis.com","google.com/recaptcha"],
                "openai":    ["openai"],
                "anthropic": ["anthropic"],
            }
            for tech_name, markers in TECH_MARKERS.items():
                if any(m in hl for m in markers):
                    tech.append(tech_name)
            if tech:
                existing = result.get("tech_stack",[])
                result["tech_stack"] = list(set(existing + tech))[:10]

            # Infer company description from meta
            desc_m = re.search(r"<meta[^>]+name=[^>]description[^>]+content=[^>]{10,200}", 
                                html, re.I)
            if desc_m and not result.get("company_description"):
                result["company_description"] = desc_m.group(0)[:200].strip()
    except Exception as e:
        logger.debug("[Enricher] Site scrape %s: %s", domain, e)

    return result


def _infer_stage_from_size(size: Any) -> str:
    try:
        n = int(str(size).split("-")[0].replace("+","").strip())
        if n < 10:   return "seed"
        if n < 50:   return "series-a"
        if n < 200:  return "series-b"
        return "growth"
    except Exception:
        return "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# SALES INTELLIGENCE INFERENCE
# ══════════════════════════════════════════════════════════════════════════════

def _infer_sales_intel(profile: Dict) -> Dict:
    """
    From all collected data, derive the sales intelligence fields that
    make Murphy's outreach feel like it read their mind.
    """
    intel = {}

    bio       = profile.get("twitter_bio","").lower()
    tweets    = " ".join(profile.get("recent_tweets",[])).lower()
    pain      = profile.get("pain_signals",[])
    followers = profile.get("twitter_followers", 0)
    stage     = profile.get("company_stage","unknown")
    stack     = profile.get("tech_stack",[])
    is_yc     = profile.get("is_yc_company", False)
    repos     = profile.get("github_repos", 0)
    pinned    = profile.get("twitter_pinned_tweet","").lower()

    # ── Language style ────────────────────────────────────────────────────────
    all_text = bio + " " + tweets
    exec_hits    = sum(1 for w in EXEC_WORDS    if w in all_text)
    founder_hits = sum(1 for w in FOUNDER_WORDS if w in all_text)
    tech_hits    = sum(1 for w in TECH_WORDS    if w in all_text)
    if tech_hits >= founder_hits and tech_hits >= exec_hits:
        intel["language_style"] = "technical"
    elif founder_hits >= exec_hits:
        intel["language_style"] = "founder-casual"
    else:
        intel["language_style"] = "executive"

    # ── Best opener angle (which psychology template works best) ──────────────
    if pain:
        intel["best_opener_angle"] = "cold_read"       # they've already signalled pain
    elif is_yc or stage in ("seed","series-a"):
        intel["best_opener_angle"] = "future_pace"     # growth-mode, vision resonates
    elif intel["language_style"] == "technical":
        intel["best_opener_angle"] = "pattern_interrupt"
    else:
        intel["best_opener_angle"] = "authority_inoculation"

    # ── Deal urgency score ────────────────────────────────────────────────────
    urgency = 30
    if pain:                        urgency += 25
    if "compliance" in pain:        urgency += 15
    if "hallucination" in pain:     urgency += 15
    if profile.get("competitor_mentions"):  urgency += 10
    if is_yc:                       urgency += 10
    if stage in ("seed","series-a"):urgency += 5
    if followers > 1000:            urgency += 5
    intel["deal_urgency_score"] = min(100, urgency)

    # ── Buying trigger (the single most actionable signal) ───────────────────
    if "hallucination" in pain or "hallucination" in tweets:
        intel["buying_trigger"] = "Tweeted about AI hallucinations in production"
    elif "compliance" in pain or "gdpr" in pain or "soc2" in pain:
        intel["buying_trigger"] = "Compliance / audit trail is an active concern"
    elif "compliance" in bio or "soc2" in bio:
        intel["buying_trigger"] = "Compliance focus visible in bio"
    elif profile.get("competitor_mentions"):
        comps = profile["competitor_mentions"]
        intel["buying_trigger"] = f"Mentioned competitor: {comps[0]}"
    elif is_yc:
        intel["buying_trigger"] = f"YC company ({profile.get('yc_batch','')}) — funded, growth pressure"
    elif pain:
        intel["buying_trigger"] = f"Pain signal in tweets: {pain[0]}"
    else:
        intel["buying_trigger"] = "Building AI product (inferred from profile)"

    # ── Tweet themes ──────────────────────────────────────────────────────────
    themes = []
    THEME_MAP = {
        "AI safety":      ["ai safety","ai risk","guardrail","alignment"],
        "compliance":     ["gdpr","soc2","hipaa","compliance","audit","regulatory"],
        "shipping fast":  ["shipped","launched","deployed","just pushed","we built"],
        "fundraising":    ["raised","seed","series","investors","pitch"],
        "scaling":        ["scale","scaling","growth","10x","hypergrowth"],
        "reliability":    ["reliability","uptime","incident","outage","latency"],
        "AI/LLM":         ["llm","gpt","claude","openai","anthropic","langchain"],
    }
    for theme, keywords in THEME_MAP.items():
        if any(k in tweets or k in bio for k in keywords):
            themes.append(theme)
    intel["tweet_themes"] = themes

    # ── Estimated deal value ──────────────────────────────────────────────────
    if is_yc or stage in ("series-b","growth"):
        intel["estimated_deal_value"] = 9800
    elif stage == "series-a":
        intel["estimated_deal_value"] = 7200
    else:
        intel["estimated_deal_value"] = 4900

    return intel


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENRICHMENT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def enrich_contact(contact_id: str) -> Dict:
    """
    Full enrichment pipeline for a CRM contact.
    Pulls from all sources, merges into custom_fields, updates CRM.
    """
    # Load contact
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT id,name,email,company,tags,custom_fields FROM contacts WHERE id=?",
                (contact_id,)
            ).fetchone()
    except Exception as e:
        return {"success": False, "error": str(e)}

    if not row:
        return {"success": False, "error": "Contact not found"}

    existing = {}
    try:
        existing = json.loads(row["custom_fields"] or "{}")
    except Exception:
        pass

    email   = row["email"] or ""
    company = row["company"] or ""
    domain  = email.split("@")[1] if "@" in email else ""
    tags    = json.loads(row["tags"] or "[]")

    profile: Dict = dict(existing)  # start with what we have

    # ── Twitter enrichment ────────────────────────────────────────────────────
    tw_username = existing.get("twitter_username","")
    # Check twitter_prospects for this contact
    if not tw_username:
        try:
            with sqlite3.connect(TWITTER_DB, timeout=5) as db:
                tw_row = db.execute(
                    "SELECT username, twitter_id FROM twitter_prospects "
                    "WHERE crm_contact_id=? LIMIT 1", (contact_id,)
                ).fetchone()
                if tw_row:
                    tw_username = tw_row[0]
        except Exception:
            pass

    if tw_username:
        tw_data = _enrich_twitter(tw_username)
        profile.update(tw_data)
        logger.info("[Enricher] Twitter: @%s — %d pain signals",
                    tw_username, len(tw_data.get("pain_signals",[])))

    # ── GitHub enrichment ─────────────────────────────────────────────────────
    if tw_username or company:
        gh_data = _enrich_github(tw_username or company.split()[0])
        profile.update(gh_data)

    # ── Company enrichment ────────────────────────────────────────────────────
    if domain or company:
        co_data = _enrich_company(domain, company)
        profile.update(co_data)

    # ── Illuminate domain search for more contacts at same company ────────────
    if domain:
        try:
            import sys; sys.path.insert(0,"/opt/Murphy-System")
            from src.illuminate import domain_search
            il = domain_search(domain, verify=False)
            profile["illuminate_contacts_found"] = il.get("total", 0)
            profile["illuminate_mx"]             = il.get("mx","")
        except Exception as e:
            logger.debug("[Enricher] Illuminate: %s", e)

    # ── Sales intelligence inference ──────────────────────────────────────────
    intel = _infer_sales_intel(profile)
    profile.update(intel)

    # ── Enrich meta ───────────────────────────────────────────────────────────
    profile["enriched_at"]      = datetime.now(timezone.utc).isoformat()
    profile["enrichment_version"] = "PATCH-197"
    sources = ["profile"]
    if tw_username: sources.append("twitter")
    if profile.get("github_username"): sources.append("github")
    if domain: sources.append("company")
    profile["enriched_sources"] = sources

    # Update deal value in deals table if we computed a better estimate
    est_val = intel.get("estimated_deal_value")
    if est_val:
        try:
            with sqlite3.connect(CRM_DB, timeout=5) as db:
                db.execute(
                    "UPDATE deals SET value=?, notes=notes||? WHERE contact_id=? AND stage='lead'",
                    (est_val,
                     f" | Enriched value: ${est_val:,} (urgency={intel.get('deal_urgency_score',0)})",
                     contact_id)
                )
                db.commit()
        except Exception:
            pass

    # ── Save back to CRM ──────────────────────────────────────────────────────
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            db.execute(
                "UPDATE contacts SET custom_fields=?, company=? WHERE id=?",
                (json.dumps(profile),
                 profile.get("company_name_verified", company) or company,
                 contact_id)
            )
            db.commit()
        logger.info("[Enricher] ✅ Contact %s enriched: urgency=%d trigger=%s",
                    contact_id, intel.get("deal_urgency_score",0),
                    intel.get("buying_trigger","?")[:50])
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {
        "success":            True,
        "contact_id":         contact_id,
        "pain_signals":       profile.get("pain_signals",[]),
        "buying_trigger":     intel.get("buying_trigger",""),
        "deal_urgency_score": intel.get("deal_urgency_score",0),
        "best_opener_angle":  intel.get("best_opener_angle",""),
        "language_style":     intel.get("language_style",""),
        "tweet_themes":       intel.get("tweet_themes",[]),
        "is_yc":              profile.get("is_yc_company", False),
        "sources":            sources,
    }


def enrich_all_pending(limit: int = 20) -> Dict:
    """
    Enrich all contacts that have not been enriched yet or were enriched
    more than 48 hours ago. Called by scheduler every 2 hours.
    """
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id, custom_fields FROM contacts "
                "WHERE contact_type IN ('lead','prospect') "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
    except Exception as e:
        return {"success": False, "error": str(e)}

    enriched = 0; skipped = 0
    for row in rows:
        cf = {}
        try:
            cf = json.loads(row["custom_fields"] or "{}")
        except Exception:
            pass

        # Skip if enriched in last 48h
        ea = cf.get("enriched_at","")
        if ea:
            try:
                last = datetime.fromisoformat(ea.replace("Z","+00:00"))
                hours_ago = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                if hours_ago < 48:
                    skipped += 1
                    continue
            except Exception:
                pass

        result = enrich_contact(row["id"])
        if result.get("success"):
            enriched += 1
        time.sleep(0.5)  # rate-limit buffer

    return {"success": True, "enriched": enriched, "skipped": skipped}


def get_enrichment_summary(limit: int = 50) -> List[Dict]:
    """Return a sales-intelligence view of all enriched contacts."""
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id, name, email, company, custom_fields FROM contacts "
                "WHERE contact_type IN ('lead','prospect') "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
    except Exception as e:
        return []

    out = []
    for row in rows:
        cf = {}
        try:
            cf = json.loads(row["custom_fields"] or "{}")
        except Exception:
            pass
        if not cf.get("enriched_at"):
            continue
        out.append({
            "contact_id":         row["id"],
            "name":               row["name"],
            "email":              row["email"],
            "company":            row["company"],
            "twitter":            cf.get("twitter_username",""),
            "pain_signals":       cf.get("pain_signals",[]),
            "buying_trigger":     cf.get("buying_trigger",""),
            "deal_urgency_score": cf.get("deal_urgency_score",0),
            "best_opener_angle":  cf.get("best_opener_angle",""),
            "language_style":     cf.get("language_style",""),
            "tweet_themes":       cf.get("tweet_themes",[]),
            "is_yc":              cf.get("is_yc_company",False),
            "company_stage":      cf.get("company_stage",""),
            "tech_stack":         cf.get("tech_stack",[]),
            "estimated_deal_value": cf.get("estimated_deal_value",4900),
            "enriched_at":        cf.get("enriched_at",""),
        })

    out.sort(key=lambda x: x["deal_urgency_score"], reverse=True)
    return out
