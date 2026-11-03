"""Exercise a candidate with a temporary DB, or check the active service read-only."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.app import load_env


def request(origin, path, key=None, body=None):
    headers = {'X-API-Key': key} if key else {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(origin + path, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)


def verify(origin, write_test_data):
    load_env()
    admin = os.environ['ADMIN_API_KEY']
    keys = json.loads(os.environ['DEVICE_KEYS_JSON'])
    assert request(origin, '/health')['status'] == 'ok'
    assert isinstance(request(origin, '/api/employees', admin), list)
    try:
        request(origin, '/api/attendance')
    except urllib.error.HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError('Attendance accessible without a key')
    if write_test_data:
        device, device_key = next(iter(keys.items()))
        request(origin, '/api/employees', admin, {'code': 'PREFLIGHT', 'name': 'Temporary preflight'})
        request(origin, '/api/bindings', admin, {'device_id': device, 'template_id': 1, 'employee_code': 'PREFLIGHT'})
        event = dict(event_id='preflight-000001', device_id=device, template_id=1, action='IN',
                     occurred_at=None, confidence=100, uptime_ms=1234)
        assert request(origin, '/api/events', device_key, event)['status'] == 'recorded'
        assert request(origin, '/api/events', device_key, event)['status'] == 'duplicate'
        assert len(request(origin, '/api/attendance', admin)) == 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.live:
        verify('http://127.0.0.1:8000', False)
        print('Live health, admin access, and unauthorized-access checks passed.')
        return
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='attendance-preflight-') as temporary:
        env = dict(os.environ, DATABASE_PATH=str(Path(temporary) / 'test.sqlite3'))
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app:create_app', '--factory',
                                    '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            origin = f'http://127.0.0.1:{port}'
            for _ in range(100):
                try:
                    request(origin, '/health')
                    break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError(process.stderr.read().decode())
                    time.sleep(0.1)
            else:
                raise RuntimeError('Candidate service did not start')
            verify(origin, True)
        finally:
            process.terminate()
            process.communicate(timeout=10)
    print('Candidate passed HTTP, authentication, staff mapping, attendance, and retry checks on a temporary database.')


if __name__ == '__main__':
    main()
