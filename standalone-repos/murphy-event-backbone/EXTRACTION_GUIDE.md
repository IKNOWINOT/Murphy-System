# Extraction Guide — murphy-event-backbone

Step-by-step instructions for publishing `murphy-event-backbone` as a
standalone GitHub repository and PyPI package.

---

## Step 1 — Create the GitHub repository

1. Go to <https://github.com/new>
2. Repository name: `murphy-event-backbone`
3. Description: `Durable in-process event bus with pub/sub, circuit breakers, DLQ, and retry. Zero dependencies.`
4. Set to **Public**
5. Do **not** initialise with a README, .gitignore, or licence (the files are already here)
6. Click **Create repository**

---

## Step 2 — Copy files and push

```bash
# From the Murphy-System repo root
cp -r standalone-repos/murphy-event-backbone /tmp/murphy-event-backbone
cd /tmp/murphy-event-backbone

git init
git add .
git commit -m "Initial extraction from Murphy System v0.1.0"
git branch -M main
git remote add origin https://github.com/IKNOWINOT/murphy-event-backbone.git
git push -u origin main
```

---

## Step 3 — Add GitHub topics

Go to **Settings → Topics** (the gear icon on the repo homepage) and add:

```
event-bus
pub-sub
circuit-breaker
dead-letter-queue
retry
event-driven
ai-agents
message-queue
backpressure
idempotent
python
zero-dependency
```

---

## Step 4 — Set up GitHub Sponsors

1. Go to <https://github.com/sponsors/IKNOWINOT>
2. Enable Sponsors on the account if not already done
3. The `FUNDING.yml` file already points to `github: IKNOWINOT`
4. After enabling, the **Sponsor** button will appear on the repo

---

## Step 5 — PyPI trusted publisher setup

1. Log in to <https://pypi.org>
2. Go to **Account Settings → Publishing → Add a new pending publisher**
3. Fill in:
   - **PyPI project name:** `murphy-event-backbone`
   - **Owner:** `IKNOWINOT`
   - **Repository:** `murphy-event-backbone`
   - **Workflow filename:** `publish.yml`
   - **Environment name:** `pypi`
4. Click **Add**
5. Back on GitHub, go to **Settings → Environments → New environment**
   - Name: `pypi`
   - No extra protection rules needed for a personal repo
6. Create a release (Step 7) — the publish workflow will fire automatically

---

## Step 6 — Enable Discussions

1. Go to **Settings → General → Features**
2. Check **Discussions**
3. Click **Save**

This enables the community Q&A tab on the repo.

---

## Step 7 — Create v0.1.0 release

1. Go to **Releases → Draft a new release**
2. **Choose a tag:** type `v0.1.0` and select "Create new tag: v0.1.0 on publish"
3. **Release title:** `murphy-event-backbone v0.1.0 — Initial release`
4. **Description:**

   ```markdown
   First standalone release of `murphy-event-backbone`, extracted from the
   [Murphy System](https://github.com/IKNOWINOT/Murphy-System).

   ### What's included
   - Pub/sub with string event types (define your own vocabulary)
   - Circuit breakers per handler
   - Dead letter queue (bounded, inspectable)
   - Retry with configurable `max_retries`
   - Idempotent `publish_event()` with duplicate detection
   - Disk persistence (atomic JSON writes)
   - Backpressure detection (`system.backpressure` events)
   - Optional background processing loop (daemon thread)
   - Thread-safe throughout
   - Zero external dependencies — stdlib only
   - 41 tests across 13 test classes

   ### Install
   \`\`\`bash
   pip install murphy-event-backbone
   \`\`\`
   ```

5. Leave **Pre-release** unchecked
6. Leave **Create a discussion** unchecked (until Discussions is enabled)
7. Click **Publish release**

The `publish.yml` workflow will build and upload to PyPI automatically.

---

## Step 8 — Post to communities

Once the package is live on PyPI, post announcements to:

- **r/Python** — "Show HN"-style post: "murphy-event-backbone — production event bus for Python AI agents, zero deps"
- **Hacker News** — Show HN post
- **Python Discord** — `#projects` channel
- **Dev.to** — article: "How we extracted a production event bus from an AI agent system"
- **X / Twitter** — tag `#Python #EventDriven #AIAgents`

---

## Step 9 — SEO checklist

- [ ] Repository description is set (Step 1)
- [ ] Topics are set (Step 3)
- [ ] Homepage URL: `https://github.com/IKNOWINOT/Murphy-System`
- [ ] README has package name in `<h1>` (badges section)
- [ ] PyPI project description matches README intro
- [ ] PyPI keywords include: `event-bus`, `pub-sub`, `circuit-breaker`, `dead-letter-queue`
- [ ] Social preview image uploaded (Settings → Social preview)

---

## Step 10 — Link back to Murphy System

Add a section to the **Murphy System README** (root `README.md`) under a
"Standalone libraries" heading:

```markdown
## Standalone libraries

Components extracted from Murphy System as standalone PyPI packages:

| Package | Description |
|---------|-------------|
| [murphy-confidence](https://github.com/IKNOWINOT/murphy-confidence) | Multi-factor confidence scoring for AI decisions |
| [murphy-event-backbone](https://github.com/IKNOWINOT/murphy-event-backbone) | Durable in-process event bus with pub/sub, circuit breakers, DLQ |
```

---

## Verification checklist

- [ ] `pip install murphy-event-backbone` succeeds
- [ ] `from murphy_event_backbone import EventBackbone, Event, CircuitBreaker` works
- [ ] CI is green on GitHub Actions
- [ ] PyPI page shows correct metadata
- [ ] Discussions tab is visible on GitHub
