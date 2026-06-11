"""Pilot run — 10 diverse inquiries, streaming results to disk."""
import sys, json, time, os
sys.path.insert(0, "/opt/Murphy-System")
from src.deliverable_evaluator import generate_murphy_reply, evaluate

OUT_DIR = "/opt/Murphy-System/quality_run_31ad"
PROGRESS = f"{OUT_DIR}/pilot_progress.jsonl"
RESULTS  = f"{OUT_DIR}/pilot_results.json"
LOG      = f"{OUT_DIR}/pilot.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

with open(f"{OUT_DIR}/inquiries.json") as f:
    all_inquiries = json.load(f)

# Sample 10 diverse — 1 per category, first 10 distinct cats
sampled = []
seen = set()
import random
random.seed(42)
for q in random.sample(all_inquiries, len(all_inquiries)):
    if q['cat'] not in seen:
        sampled.append(q); seen.add(q['cat'])
    if len(sampled) == 10:
        break

log(f"START pilot n={len(sampled)}")
results = []
open(PROGRESS, "w").close()

for i, inq in enumerate(sampled, 1):
    log(f"[{i}/10] {inq['id']} {inq['cat']}/{inq['subcat']} trap={inq['trap']}")
    t0 = time.time()
    try:
        reply = generate_murphy_reply(inq)
        if reply.startswith("[error"):
            log(f"  GEN_FAIL: {reply[:120]}")
            continue
        log(f"  reply: {len(reply)} chars in {time.time()-t0:.1f}s")
        e = evaluate(inq, reply)
        elapsed = time.time() - t0
        log(f"  EVAL median={e['median']:.1f} min={e['min']:.1f} ships={e['ships']} ({elapsed:.0f}s)")
        log(f"    scores: " + " ".join(f"{k[:4]}={v:.1f}" for k,v in e['scores'].items()))
        rec = {"id":inq['id'],"cat":inq['cat'],"subcat":inq['subcat'],"trap":inq['trap'],
               "reply":reply,"evaluation":e,"elapsed_s":round(elapsed,1)}
        results.append(rec)
        with open(PROGRESS, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as ex:
        log(f"  EXCEPTION: {ex}")

with open(RESULTS, "w") as f:
    json.dump(results, f, indent=2)
log(f"DONE n_complete={len(results)}")

# Aggregate
if results:
    by_lens = {}
    for r in results:
        for lens, score in r['evaluation']['scores'].items():
            by_lens.setdefault(lens, []).append(score)
    log("── BASELINE ──")
    for lens, scores in by_lens.items():
        log(f"  {lens:18s} avg={sum(scores)/len(scores):.2f}  min={min(scores):.0f}  max={max(scores):.0f}")
    medians = [r['evaluation']['median'] for r in results]
    ships = sum(1 for r in results if r['evaluation']['ships'])
    log(f"overall median: {sum(medians)/len(medians):.2f}")
    log(f"ships: {ships}/{len(results)}")
