"""Start a temporary real HTTP server and check health, UI, and access control."""
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def main():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app:create_app', '--factory',
                                '--host', '127.0.0.1', '--port', str(port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        origin = f'http://127.0.0.1:{port}'
        for _ in range(50):
            try:
                with urllib.request.urlopen(origin + '/health', timeout=1) as response:
                    assert response.status == 200
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError(process.stderr.read().decode())
                time.sleep(0.1)
        else:
            raise RuntimeError('Server did not become ready')
        with urllib.request.urlopen(origin + '/', timeout=2) as response:
            assert b'Admin sign in' in response.read()
        for path in ('/api/attendance', '/api/me', '/api/live'):
            try:
                urllib.request.urlopen(origin + path, timeout=2)
                raise AssertionError(f'Unauthenticated {path} was accessible')
            except urllib.error.HTTPError as error:
                assert error.code == 401
        print('Real HTTP smoke check passed: health, login page, protected attendance, session and live stream.')
    finally:
        process.terminate()
        process.communicate(timeout=10)


if __name__ == '__main__':
    main()
