# Murphy Conductor (R510 series)

A small orchestration layer between user intent and Murphy's APIs.

## Endpoints
- `GET  /health` — service health
- `POST /conduct` `{ask: str}` — single-cycle plan + execute
- `POST /conduct-and-reply` `{message: str}` — chat reply + conductor in parallel
- `GET  /conduct/job/{job_id}` — fetch a past job
- `GET  /conduct/jobs?limit=N` — recent jobs

## Pipeline
1. **PSM proposal** — every job filed with full ask (audit chain).
2. **Concept extraction** — top-5 keywords from ask.
3. **Repo grep** — concepts → file:line context (max 15 hits).
4. **Murphy plan** — LLM reasons over (ask + concepts + context).
5. **Tool registry lookup** — `/api/tools/search?q=<concept>` for real endpoints.
6. **Murphy chooses** — picks ONE endpoint from registry (cannot invent).
7. **Execute** — GETs run; POSTs route to HITL via PSM (never inline).
8. **Persist** — job + result saved to `conductor_jobs.db`.

## Files
- Service: `/opt/Murphy-System/scripts/conductor_service.py` (port 8091)
- Library: `/opt/Murphy-System/scripts/conductor.py`
- Systemd: `/etc/systemd/system/murphy-conductor.service`
- Env: `/var/lib/murphy-production/secrets/conductor.env`
- DB: `/var/lib/murphy-production/state/conductor_jobs.db`

## Design intent
- **No invented endpoints** — Murphy MUST pick from tool registry.
- **POSTs are HITL by default** — filed as `hitl_review_*` PSM proposals.
- **PSM is the audit chain** — every ask → seq number → ledger entry.
- **Honest failures** — if parse fails, error reported, no fake success.
