
# multimodal_describer_bot — Budget-aware multimodal descriptions (Bot-standards compliant)

**Scope:** deterministic features + optional OCR/ASR/captions via `model_proxy` (stubbed here). Includes privacy redaction, caching, GP hooks, S(t), and budgets/quotas.

## Tasks
- `describe|features|caption|ocr|asr|keyframes|summarize|embed`

## Input attachments
- `image`: `text` may contain JSON pixel array (HxWx3); optionally `bytes_b64` for proxy calls.
- `audio`: `text` may contain JSON int samples array.
- `video`: `text` may contain JSON array of frames (each HxWx3).
- `text`: `text` content summarized.

## Register
- run: `src/clockwork/bots/multimodal_describer_bot/multimodal_describer_bot.ts::run`
- ping: `src/clockwork/bots/multimodal_describer_bot/rollcall.ts::ping`
