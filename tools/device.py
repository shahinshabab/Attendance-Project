"""USB bridge and physical maintenance commands. Run from the project root."""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import serial

from backend.app import load_env
import os


def deliver(server, key, event):
    url = server.rstrip('/') + '/api/events'
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('Use HTTPS for a remote server; HTTP is allowed only on localhost')
    request = urllib.request.Request(url, data=json.dumps(event).encode(),
                                    headers={'Content-Type': 'application/json', 'X-API-Key': key}, method='POST')
    # Reject redirects so a device credential is never forwarded to a different origin.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    with urllib.request.build_opener(NoRedirect).open(request, timeout=8) as response:
        result = json.load(response)
    return result.get('event_id') == event['event_id'] and result.get('status') in ('recorded', 'duplicate', 'unmapped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--server', default='http://127.0.0.1:8765')
    parser.add_argument('command', choices=['bridge', 'enroll', 'delete', 'status', 'in', 'out'])
    parser.add_argument('--slot', type=int)
    args = parser.parse_args()
    if args.command in ('enroll', 'delete') and (args.slot is None or not 1 <= args.slot <= 1000):
        parser.error('--slot must be 1..1000')
    load_env()
    keys = json.loads(os.getenv('DEVICE_KEYS_JSON', '{}'))
    with serial.Serial(args.port, 115200, timeout=1) as port:
        time.sleep(2)  # Most development boards reset when the port opens.
        port.write(f'TIME {int(time.time())}\n'.encode())
        if args.command != 'bridge':
            command = args.command.upper() + (f' {args.slot}' if args.slot else '')
            port.write((command + '\n').encode())
        print('USB connected. Ctrl+C closes the port. Do not open another serial monitor.')
        deadline = time.monotonic() + (180 if args.command == 'enroll' else 8)
        next_sync = time.monotonic() + 60
        while args.command == 'bridge' or time.monotonic() < deadline:
            line = port.readline().decode(errors='replace').strip()
            if time.monotonic() > next_sync:
                port.write(f'TIME {int(time.time())}\n'.encode())
                next_sync = time.monotonic() + 60
            if not line:
                continue
            try:
                packet = json.loads(line)
            except json.JSONDecodeError:
                print(line)
                continue
            if packet.get('type') != 'attendance' or args.command != 'bridge':
                print(line, flush=True)
                if args.command == 'enroll' and packet.get('type') == 'status':
                    message = packet.get('message', '')
                    if message.startswith('Enrolled slot '):
                        return
                    if message.startswith(('Invalid slot', 'Slot occupied', 'Could not confirm',
                                           'First capture failed', 'Removal timed out', 'Enrollment failed')):
                        raise RuntimeError(message)
                continue
            event = packet['event']
            key = keys.get(event.get('device_id'))
            if not key:
                print('No key configured for device; scan remains queued.')
                continue
            try:
                if deliver(args.server, key, event):
                    port.write(('ACK ' + event['event_id'] + '\n').encode())
                    print('Saved:', event['event_id'])
                else:
                    print('Unexpected server response; scan remains queued.')
            except (OSError, ValueError, urllib.error.URLError) as error:
                print('Server unavailable or rejected event; scan remains queued:', error)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
