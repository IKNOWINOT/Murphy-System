
#!/usr/bin/env python3
import os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
HOST=os.environ.get('VAL_HOST','127.0.0.1'); PORT=int(os.environ.get('VAL_PORT','8775')); OUT=os.environ.get('VAL_OUT','runs.ndjson')
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(n).decode('utf-8')
        try:
            data = json.loads(body or '{}')
        except (json.JSONDecodeError, ValueError):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'bad_json'}).encode('utf-8'))
            return
        with open(OUT, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data) + '\n')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{}')
def main(): HTTPServer((HOST,PORT),H).serve_forever()
if __name__=='__main__': main()
