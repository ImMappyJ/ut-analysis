"""Read-only loopback preview of exactly one HTML file; no directory browsing."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def server_for(path, port=0):
    report = Path(path).resolve()
    if not report.is_file():
        raise FileNotFoundError(report)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split('?', 1)[0] not in ('/', '/report.html'):
                self.send_error(404)
                return
            try:
                payload = report.read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    with server_for(args.report, args.port) as server:
        print(f'http://127.0.0.1:{server.server_port}/report.html', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
