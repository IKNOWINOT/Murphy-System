
#!/usr/bin/env python3
import os, json, time
from http.server import HTTPServer, BaseHTTPRequestHandler
HOST=os.environ.get('RELAY_HOST','127.0.0.1'); PORT=int(os.environ.get('RELAY_PORT','8765'))
TOKEN=os.environ.get('GHOST_RELAY_TOKEN','dev-token'); OUT=os.environ.get('RELAY_OUT','queue.ndjson')
class H(BaseHTTPRequestHandler):
    def _ok(self,code=200,p=None): self.send_response(code); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(json.dumps(p or {'ok':True}).encode())
    def do_POST(self):
        try:
            if self.headers.get('X-Relay-Token')!=TOKEN: self._ok(403,{'ok':False,'error':'forbidden'}); return
            n=int(self.headers.get('Content-Length','0')); data=json.loads(self.rfile.read(n) or '{}'); ev=data.get('events') or []; ts=time.time()
            with open(OUT,'a',encoding='utf-8') as f:
                for e in ev: f.write(json.dumps({'ts_recv':ts, **e})+'\n')
            self._ok(200,{'ok':True,'count':len(ev)})
        except Exception as e: self._ok(400,{'ok':False,'error':str(e)})
def main(): HTTPServer((HOST,PORT),H).serve_forever()
if __name__=='__main__': main()
