import http.server
import socketserver
import requests

PORT = 8000

class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Inject CORS headers into everything we serve
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-MBX-APIKEY, Content-Type, Accept')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        # Intercept proxy requests starting with /proxy/
        if self.path.startswith('/proxy/'):
            # The remaining path is the target URL (e.g. https://testnet.binancefuture.com/...)
            target_url = self.path[7:]
            
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len)

            headers = {}
            if 'X-MBX-APIKEY' in self.headers:
                headers['X-MBX-APIKEY'] = self.headers['X-MBX-APIKEY']
            if 'Content-Type' in self.headers:
                headers['Content-Type'] = self.headers['Content-Type']

            try:
                resp = requests.post(target_url, data=post_body, headers=headers, timeout=15)
                self.send_response(resp.status_code)
                for key, value in resp.headers.items():
                    # Pass through safe headers
                    if key.lower() not in ['content-encoding', 'transfer-encoding', 'content-length', 'connection']:
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(resp.content)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            return super().do_POST()

print(f"Starting Local Proxy UI Server on http://localhost:{PORT}")
print("1. Open http://localhost:8000/ui.html in your browser")
print("2. CORS is fully unblocked!")
print("-" * 50)

with socketserver.TCPServer(("", PORT), ProxyHTTPRequestHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
