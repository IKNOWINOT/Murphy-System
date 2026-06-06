#!/bin/bash
# cto_consult.sh — Ask Murphy's platform_cto a question, rule-loaded.
set -euo pipefail
QUESTION="${1:-}"
if [ -z "$QUESTION" ]; then
  echo "Usage: $0 \"<question>\"" >&2; exit 1
fi

# Build whole payload in python so we don't fight bash quoting
SESSION_ID="superagent_cto_consult_$(date -u +%Y%m%dT%H%M%SZ)"
export QUESTION SESSION_ID

PAYLOAD=$(python3 <<'PY'
import importlib.util, json, os, re

spec = importlib.util.spec_from_file_location(
    'rcrl',
    '/opt/Murphy-System/src/rosetta/rosetta_cto_rules_loader.py'
)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
full = m.render_rules_for_cto()
mt = re.search(r'## Tier 2', full)
rules_block = full[:mt.start()] if mt else full

prompt = f"""You are Murphy's platform_cto. You ALWAYS follow these patch/code rules:

{rules_block}

---

Corey is asking through Superagent. Give a discerning, honest answer.
If you do not know, say so. If you need to audit something first, say
what to audit. If a Standing Decision or rule already settles it, cite it.

Question:
{os.environ['QUESTION']}
"""
print(json.dumps({"message": prompt, "session_id": os.environ['SESSION_ID']}))
PY
)

curl -sS --max-time 90 -X POST https://murphy.systems/api/chat-v2 \
  -H "Content-Type: application/json" -d "$PAYLOAD" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('reply', '(no reply)'))
print()
print(f'[provider: {d.get(\"provider_used\")}/{d.get(\"model\")}, latency: {d.get(\"latency_ms\")}ms, cost: \${d.get(\"cost_usd\", 0):.4f}]', file=sys.stderr)
"
