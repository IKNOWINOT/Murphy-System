"""
Background loop: exercise existing deliverable + codegen infrastructure
on real test prompts, score outputs, log failures for follow-up.

Reuses (per user directive: existing infrastructure first):
  - demo_deliverable_generator (HTML/PDF/DOCX/ZIP, app scaffolds)
  - production_deliverable_wizard (DeliverableWizard, DeliverableSpec)
  - deliverable_evaluator.call_llm + judge_lens + evaluate
  - smart_codegen / multi_language_codegen
  - reconciliation/output_evaluator
"""
import sys, json, time, traceback, os, hashlib
sys.path.insert(0, "/opt/Murphy-System")

OUT_DIR = "/opt/Murphy-System/quality_run_31ad/deliverable_eval"
LOG = f"{OUT_DIR}/loop.jsonl"
ARTIFACT_DIR = f"{OUT_DIR}/artifacts"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

PROMPTS = [
    # (kind, prompt, expected_format)
    ("code", "Write a Python function that takes a list of dicts with 'price' and 'quantity' keys and returns the total revenue, ignoring rows where price or quantity is missing or negative.", "py"),
    ("code", "Write a SQL query against tables `orders(id, customer_id, total, created_at)` and `customers(id, name, segment)` that returns the top 5 customer segments by total revenue in 2025.", "sql"),
    ("code", "Write a TypeScript React component for a settings form with name (text), email (email), notifications (boolean toggle), and a save button that calls onSubmit(values).", "tsx"),
    ("code", "Write a bash script that takes a directory path, finds all .log files older than 7 days, gzips them, and writes a manifest of compressed files to /tmp/log_manifest.txt.", "sh"),
    ("deliverable", "Build a 1-page executive brief for an MEP engineering firm evaluating whether to bid on a 50,000 sqft mixed-use building HVAC retrofit. Should include scope summary, risk register (5 risks), and a go/no-go recommendation with reasoning.", "md"),
    ("deliverable", "Build a Statement of Work for a 6-week engagement to migrate 3 small Postgres databases (each <50GB) to AWS RDS, including milestones, deliverables, acceptance criteria, and assumptions.", "md"),
    ("deliverable", "Build a one-page investor update for a seed-stage SaaS doing $25K MRR with 15% MoM growth, 3% monthly churn, 12 months runway, currently hiring a head of sales.", "md"),
    ("file", "Generate a Python project scaffold (3-5 files) for a CLI tool that fetches weather from openweathermap and caches it locally for 1 hour. Include a README, the main module, a cache module, tests, and requirements.txt.", "zip"),
]

def call_llm(messages, max_tokens=900, temperature=0.4):
    from src.deliverable_evaluator import call_llm as _c
    return _c(messages, max_tokens=max_tokens, temperature=temperature)

def grade(prompt, output, kind):
    """Use the existing judge_lens infrastructure to grade the output."""
    from src.deliverable_evaluator import judge_lens
    # Use 'factual_accuracy' + 'completeness' + 'usability' lenses if defined
    grades = {}
    for lens in ("factual_accuracy", "completeness", "usability"):
        try:
            inquiry = {"subject": kind, "body": prompt, "from": "test@eval"}
            g = judge_lens(inquiry, output, lens)
            grades[lens] = g
        except Exception as e:
            grades[lens] = {"error": str(e)}
    return grades

def run_one(idx, kind, prompt, ext):
    t0 = time.time()
    rec = {"idx": idx, "kind": kind, "prompt": prompt[:120], "ext": ext}
    try:
        system_msg = {
            "code": "You are a senior engineer. Output ONLY the code, with brief inline comments where useful. No prose.",
            "deliverable": "You are Murphy. Produce a clean, professional deliverable in Markdown. Use headers, bullet lists, and concrete specifics. No filler.",
            "file": "You are Murphy. Plan the file scaffold; produce each file with a fenced code block preceded by the filepath. Format: ```python\\n# FILE: path/to/file.py\\n...\\n```",
        }[kind]
        reply = call_llm(
            [{"role":"system","content": system_msg},
             {"role":"user","content": prompt}],
            max_tokens=1200, temperature=0.3,
        )
        rec["chars"] = len(reply)
        rec["preview"] = reply[:300]
        # Write the artifact
        h = hashlib.md5(prompt.encode()).hexdigest()[:8]
        artifact_path = f"{ARTIFACT_DIR}/{idx:02d}_{kind}_{h}.{ext}"
        with open(artifact_path, "w") as f:
            f.write(reply)
        rec["artifact"] = artifact_path
        # Grade
        rec["grades"] = grade(prompt, reply, kind)
        rec["elapsed_s"] = round(time.time()-t0, 1)
        rec["ok"] = True
    except Exception as e:
        rec["ok"] = False
        rec["error"] = str(e)
        rec["trace"] = traceback.format_exc()[-500:]
        rec["elapsed_s"] = round(time.time()-t0, 1)
    return rec

def main():
    open(LOG, "w").close()
    for idx, (kind, prompt, ext) in enumerate(PROMPTS):
        rec = run_one(idx, kind, prompt, ext)
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
        # Light pacing so we don't spike LLM concurrency
        time.sleep(2)

if __name__ == "__main__":
    main()
