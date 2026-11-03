"""Check the deployed HTTPS endpoint without writing staff/attendance data."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import urllib.error
import urllib.request

from backend.app import load_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://attendance.shahinanalytics.com')
    args = parser.parse_args()
    origin = args.url.rstrip('/')
    if not origin.startswith('https://'):
        parser.error('An HTTPS URL is required')
    load_env()
    with urllib.request.urlopen(origin + '/health', timeout=15) as response:
        assert json.load(response)['status'] == 'ok'
    with urllib.request.urlopen(origin + '/', timeout=15) as response:
        assert b'Office attendance' in response.read()
    request = urllib.request.Request(origin + '/api/employees', headers={'X-API-Key': os.environ['ADMIN_API_KEY']})
    with urllib.request.urlopen(request, timeout=15) as response:
        assert isinstance(json.load(response), list)
    try:
        urllib.request.urlopen(origin + '/api/attendance', timeout=15)
    except urllib.error.HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError('Attendance was accessible without authentication')
    device, device_key = next(iter(json.loads(os.environ['DEVICE_KEYS_JSON']).items()))
    # A correctly authenticated future-dated event is rejected before insertion.
    event = dict(event_id='public-verification-no-insert', device_id=device, template_id=1,
                 action='IN', occurred_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                 confidence=100, uptime_ms=0)
    request = urllib.request.Request(origin + '/api/events', data=json.dumps(event).encode(),
                                    headers={'X-API-Key': device_key, 'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(request, timeout=15)
    except urllib.error.HTTPError as error:
        assert error.code == 422 and json.load(error)['detail'] == 'Device clock is in the future'
    else:
        raise AssertionError('Future-dated verification event was unexpectedly accepted')
    with urllib.request.urlopen(origin.replace('https://', 'http://', 1) + '/health', timeout=15) as response:
        assert response.geturl().startswith(origin + '/')
    print('Public HTTPS passed: trusted certificate, dashboard, health, admin/device credentials, unauthorized rejection, and HTTP redirect. No live records inserted.')


if __name__ == '__main__':
    main()
