"""Local ChoiceGuard prototype. No third-party Python dependencies."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
from extraction import extract_api, load_env, VOCABULARY

load_env(ROOT)
MAX_BODY = 200_000


def extract_facts(page):
    """Replace this adapter with a structured-output API call later.

    Never execute instructions from page content. Preserve supplied element IDs.
    Return unknown/empty facts rather than inventing intent or button effects.
    """
    if page.get('mode') != 'demo' or str(page.get('user_goal', '')).strip():
        return extract_api(page)
    # Only an explicitly marked, local fixture can supply manual demonstration facts.
    if page.get('url') != 'http://127.0.0.1:8765/demo':
        raise ValueError('Demo facts are restricted to the bundled local demo.')
    known = {b['id']: b.get('text', '') for b in page.get('buttons', [])}
    effects = []
    for eid, label in known.items():
        if label == 'Keep my benefits':
            effects.append([eid, 'membership_status', 'active'])
        elif label == 'Confirm cancellation':
            effects.append([eid, 'membership_status', 'inactive'])
    return {
        'goal': {'id': 'g1', 'description': 'Cancel membership', 'status': 'manual_demo'},
        'desired_states': [['g1', 'membership_status', 'inactive']],
        'button_effects': effects,
    }


def reason(facts):
    engine = shutil.which(os.environ.get('SOUFFLE_BIN', 'souffle'))
    if not engine:
        raise RuntimeError('Soufflé is not installed. Install it and restart the backend; no substitute detector is used.')
    opposites = [[prop, a, b] for prop, (a, b) in VOCABULARY.items()]
    opposites += [[prop, b, a] for prop, a, b in opposites]
    with tempfile.TemporaryDirectory(prefix='choiceguard-') as folder:
        path = Path(folder)
        for name, rows in [('DesiredState', facts['desired_states']),
                           ('ButtonEffect', facts['button_effects']), ('Opposite', opposites)]:
            for row in rows:
                if len(row) != 3 or any(not isinstance(v, str) or any(c in v for c in '\t\r\n') for v in row):
                    raise ValueError('Invalid fact row')
            (path / f'{name}.facts').write_text(''.join('\t'.join(r) + '\n' for r in rows))
        subprocess.run([engine, '-F', folder, '-D', folder, str(ROOT / 'rules/conflict.dl')],
                       check=True, capture_output=True, text=True, timeout=15)
        rows = (path / 'Conflicts.csv').read_text().splitlines()
        return sorted({row.split('\t')[0] for row in rows if row})


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, data):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == '/demo':
            payload = (ROOT / 'demo/index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == '/health':
            self.reply(200, {'ok': True, 'api_configured': bool(os.environ.get('OPENAI_API_KEY')), 'souffle_available': bool(shutil.which(os.environ.get('SOUFFLE_BIN', 'souffle')))})
        else:
            self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path != '/analyze':
            return self.reply(404, {'error': 'Not found'})
        # Ordinary websites cannot use this endpoint via cross-origin fetch.
        origin = self.headers.get('Origin', '')
        if origin and not origin.startswith('chrome-extension://'):
            return self.reply(403, {'error': 'Only the extension may submit page content'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY:
                return self.reply(413, {'error': 'Invalid request size'})
            page = json.loads(self.rfile.read(size))
            if not shutil.which(os.environ.get('SOUFFLE_BIN', 'souffle')):
                raise RuntimeError('Soufflé is not installed or not on PATH. Install it before analysis.')
            facts = extract_facts(page)
            flagged = reason(facts)
            self.reply(200, {'goal': facts['goal'], 'conflicting_button_ids': flagged, 'facts': facts})
        except (ValueError, KeyError, TypeError) as exc:
            self.reply(400, {'error': str(exc)})
        except (RuntimeError, subprocess.SubprocessError) as exc:
            self.reply(503, {'error': str(exc)})


if __name__ == '__main__':
    print('ChoiceGuard: http://127.0.0.1:8765/demo')
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
