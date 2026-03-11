
#!/usr/bin/env python3
import os, json, argparse
def load_ndjson(p):
    arr=[]; 
    if not os.path.exists(p): return arr
    with open(p,'r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: arr.append(json.loads(line))
            except (json.JSONDecodeError, ValueError): pass
    return arr
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--events',default='queue.ndjson'); ap.add_argument('--runs',default='runs.ndjson'); ap.add_argument('--out',default='dashboard.html'); a=ap.parse_args()
    ev=load_ndjson(a.events); rn=load_ndjson(a.runs)
    idle=sum(1 for e in ev if e.get('kind')=='idle'); focus=sum(1 for e in ev if e.get('kind')=='focus'); keys=sum(1 for e in ev if e.get('kind')=='key'); mouse=sum(1 for e in ev if e.get('kind')=='mouse')
    passes=sum(1 for r in rn if r.get('passed')); total=len(rn)
    html=f"""<html><head><meta charset='utf-8'><title>Ghost Metrics</title></head>
      <body><h1>Ghost Metrics</h1>
      <p>Events: {len(ev)} | Keys: {keys} | Mouse: {mouse} | Focus: {focus} | Idle: {idle}</p>
      <p>Microtask pass rate: {passes}/{total}</p>
      <h2>Recent Events</h2><pre>{json.dumps(ev[-25:], indent=2)}</pre>
      <h2>Validation Runs</h2><pre>{json.dumps(rn[-25:], indent=2)}</pre>
      </body></html>"""
    with open(a.out,'w',encoding='utf-8') as f: f.write(html)
    print('[dashboard] wrote', a.out)
if __name__=='__main__': main()
