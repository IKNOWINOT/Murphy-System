import sys, json, time, os
sys.path.insert(0, "/opt/Murphy-System")
from src.deliverable_evaluator import call_llm
from src.stranger_responder import DEFAULT_MURPHY_SOUL

OUT = "/opt/Murphy-System/quality_run_31ad/after_31af.jsonl"
open(OUT, "w").close()

with open("/opt/Murphy-System/quality_run_31ad/pilot_progress.jsonl") as f:
    pilot = [json.loads(line) for line in f]
with open("/opt/Murphy-System/quality_run_31ad/inquiries.json") as f:
    all_inq = {q["id"]: q for q in json.load(f)}

for p in pilot:
    inq = all_inq[p["id"]]
    user_msg = f"INQUIRY SUBJECT: {inq.get('subject','')}\nINQUIRY FROM: {inq.get('from','')}\nINQUIRY BODY:\n{inq['body']}\n\nWrite your reply now."
    t0 = time.time()
    reply = call_llm(
        [{"role":"system","content": DEFAULT_MURPHY_SOUL},
         {"role":"user","content": user_msg}],
        max_tokens=700, temperature=0.5,
    )
    rec = {"id":p["id"], "cat":p["cat"], "trap":p["trap"],
           "old_reply":p["reply"], "new_reply":reply,
           "old_chars":len(p["reply"]), "new_chars":len(reply),
           "elapsed_s": round(time.time()-t0, 1)}
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n")
