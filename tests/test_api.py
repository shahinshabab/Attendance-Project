import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

ADMIN = 'admin-test-key-' + 'a' * 24
DEVICE = 'device-test-key-' + 'b' * 24
HEADERS = {'X-API-Key': ADMIN}
DEVICE_HEADERS = {'X-API-Key': DEVICE}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / 'test.sqlite3', ADMIN, {'office-01': DEVICE}))


def event(**changes):
    result = dict(event_id='event-00000001', device_id='office-01', template_id=1,
                  action='IN', occurred_at='2026-01-01T23:00:00Z', confidence=120, uptime_ms=2345)
    result.update(changes)
    return result


def assign(client):
    assert client.post('/api/employees', headers=HEADERS, json={'code': 'E001', 'name': 'Test Staff'}).status_code == 200
    assert client.post('/api/bindings', headers=HEADERS, json={'device_id': 'office-01', 'template_id': 1, 'employee_code': 'E001'}).status_code == 200


def test_auth_separates_device_and_admin(client):
    assert client.get('/health').status_code == 200
    assert client.get('/api/attendance').status_code == 401
    assert client.get('/api/employees', headers=DEVICE_HEADERS).status_code == 401
    assert client.post('/api/events', headers=HEADERS, json=event()).status_code == 401
    assert client.post('/api/events', headers=DEVICE_HEADERS, json=event(device_id='other')).status_code == 401


def test_retries_are_idempotent_and_conflicts_do_not_overwrite(client):
    assign(client)
    assert client.post('/api/events', headers=DEVICE_HEADERS, json=event()).json()['status'] == 'recorded'
    assert client.post('/api/events', headers=DEVICE_HEADERS, json=event()).json()['status'] == 'duplicate'
    assert client.post('/api/events', headers=DEVICE_HEADERS, json=event(action='OUT')).status_code == 409
    rows = client.get('/api/attendance', headers=HEADERS).json()
    assert len(rows) == 1 and rows[0]['employee_code'] == 'E001'
    assert rows[0]['action'] == 'IN'


def test_concurrent_retry_stores_one_event(client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(lambda _: client.post('/api/events', headers=DEVICE_HEADERS, json=event()).status_code, range(8)))
    assert statuses == [200] * 8
    assert len(client.get('/api/attendance', headers=HEADERS).json()) == 1


def test_office_date_and_unknown_clock(client):
    client.post('/api/events', headers=DEVICE_HEADERS, json=event())
    rows = client.get('/api/attendance?day=2026-01-02', headers=HEADERS).json()
    assert len(rows) == 1 and rows[0]['local_time'].startswith('2026-01-02T04:30')
    assert client.get('/api/attendance?day=2026-01-01', headers=HEADERS).json() == []
    response = client.post('/api/events', headers=DEVICE_HEADERS, json=event(event_id='event-00000002', occurred_at=None))
    assert response.json()['status'] == 'unmapped'
    rows = client.get('/api/attendance', headers=HEADERS).json()
    assert any(r['time_source'] == 'received_only' and r['occurred_at'] is None for r in rows)
    assert client.get('/api/attendance?day=bad', headers=HEADERS).status_code == 422


def test_rejects_bad_or_future_clock(client):
    assert client.post('/api/events', headers=DEVICE_HEADERS, json=event(occurred_at='2026-01-01T12:00:00')).status_code == 422
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert client.post('/api/events', headers=DEVICE_HEADERS, json=event(occurred_at=future)).status_code == 422


def test_slot_cannot_silently_change_employee(client):
    assign(client)
    client.post('/api/employees', headers=HEADERS, json={'code': 'E002', 'name': 'Other Staff'})
    r = client.post('/api/bindings', headers=HEADERS, json={'device_id': 'office-01', 'template_id': 1, 'employee_code': 'E002'})
    assert r.status_code == 409


def test_export_escapes_spreadsheet_formulas(client):
    assign(client)
    client.post('/api/employees', headers=HEADERS, json={'code': 'E001', 'name': '=1+1'})
    client.post('/api/events', headers=DEVICE_HEADERS, json=event())
    response = client.get('/api/export.csv', headers=HEADERS)
    assert response.status_code == 200 and "'=1+1" in response.text


def test_unmapped_history_is_not_reassigned_by_later_binding(client):
    client.post('/api/events', headers=DEVICE_HEADERS, json=event())
    assign(client)
    assert client.get('/api/attendance', headers=HEADERS).json()[0]['employee_code'] is None


def sync(client, **changes):
    report = dict(device_id='office-01', network='fallback', wifi_version=0)
    report.update(changes)
    response = client.post('/api/device/sync', headers=DEVICE_HEADERS, json=report)
    assert response.status_code == 200
    return response.json()


def test_wifi_is_pushed_until_device_applies_version(client):
    assert 'wifi' not in sync(client)
    assert client.put('/api/devices/office-01/wifi', headers=HEADERS, json={'ssid': 'Office', 'password': 'short'}).status_code == 422
    assert client.put('/api/devices/other/wifi', headers=HEADERS, json={'ssid': 'Office', 'password': 'password1'}).status_code == 400
    assert client.put('/api/devices/office-01/wifi', headers=DEVICE_HEADERS, json={'ssid': 'Office', 'password': 'password1'}).status_code == 401
    saved = client.put('/api/devices/office-01/wifi', headers=HEADERS, json={'ssid': 'Office', 'password': 'password1'}).json()
    assert saved == {'device_id': 'office-01', 'ssid': 'Office', 'version': 1}
    assert sync(client)['wifi'] == {'ssid': 'Office', 'password': 'password1', 'version': 1}
    assert 'wifi' not in sync(client, wifi_version=1, network='office')
    client.put('/api/devices/office-01/wifi', headers=HEADERS, json={'ssid': 'Office', 'password': 'password2'})
    assert sync(client, wifi_version=1)['wifi']['version'] == 2
    listed = client.get('/api/devices', headers=HEADERS).json()[0]
    assert listed['wifi']['version'] == 2 and 'password' not in listed['wifi']
    assert listed['report']['network'] == 'fallback' and listed['last_seen']


def test_sync_requires_device_key_and_reports_server_time(client):
    assert client.post('/api/device/sync', headers=HEADERS, json={'device_id': 'office-01'}).status_code == 401
    assert abs(sync(client)['server_time'] - datetime.now(timezone.utc).timestamp()) < 60


def test_server_requested_enrollment_binds_slot_on_success(client):
    client.post('/api/employees', headers=HEADERS, json={'code': 'E001', 'name': 'Test Staff'})
    assert client.post('/api/enrollments', headers=HEADERS, json={'device_id': 'office-01', 'employee_code': 'NOPE'}).status_code == 404
    job = client.post('/api/enrollments', headers=HEADERS, json={'device_id': 'office-01', 'employee_code': 'E001'}).json()
    assert job['status'] == 'pending' and job['template_id'] == 1
    assert client.post('/api/enrollments', headers=HEADERS, json={'device_id': 'office-01', 'employee_code': 'E001'}).status_code == 409
    command = sync(client)['command']
    assert command == {'id': job['id'], 'type': 'enroll', 'slot': 1, 'employee_code': 'E001', 'employee_name': 'Test Staff'}
    assert sync(client)['command']['id'] == job['id']  # re-sent until a result arrives
    result = {'device_id': 'office-01', 'success': True, 'message': 'Enrolled slot 1'}
    url = f"/api/device/enrollments/{job['id']}/result"
    assert client.post(url, headers=HEADERS, json=result).status_code == 401
    assert client.post(url, headers=DEVICE_HEADERS, json=result).json() == {'id': job['id'], 'status': 'enrolled'}
    assert client.post(url, headers=DEVICE_HEADERS, json=result).json()['status'] == 'enrolled'
    assert 'command' not in sync(client)
    assert client.get('/api/bindings', headers=HEADERS).json() == [{'device_id': 'office-01', 'template_id': 1, 'employee_code': 'E001'}]
    client.post('/api/events', headers=DEVICE_HEADERS, json=event())
    assert client.get('/api/attendance', headers=HEADERS).json()[0]['employee_code'] == 'E001'


def test_failed_or_cancelled_enrollment_never_reuses_slot(client):
    assign(client)  # slot 1 already bound manually
    first = client.post('/api/enrollments', headers=HEADERS, json={'device_id': 'office-01', 'employee_code': 'E001'}).json()
    assert first['template_id'] == 2
    sync(client)
    client.post(f"/api/device/enrollments/{first['id']}/result", headers=DEVICE_HEADERS,
                json={'device_id': 'office-01', 'success': False, 'message': 'First capture failed'})
    second = client.post('/api/enrollments', headers=HEADERS, json={'device_id': 'office-01', 'employee_code': 'E001'}).json()
    assert second['template_id'] == 3
    assert client.post(f"/api/enrollments/{second['id']}/cancel", headers=HEADERS).json()['status'] == 'cancelled'
    assert client.post(f"/api/enrollments/{second['id']}/cancel", headers=HEADERS).status_code == 409
    assert 'command' not in sync(client)
    late = client.post(f"/api/device/enrollments/{second['id']}/result", headers=DEVICE_HEADERS,
                       json={'device_id': 'office-01', 'success': True, 'message': 'Enrolled slot 3'})
    assert late.json()['status'] == 'cancelled'
    statuses = {e['id']: e for e in client.get('/api/enrollments', headers=HEADERS).json()}
    assert statuses[first['id']]['status'] == 'failed' and 'unassigned' in statuses[second['id']]['message']
    assert [b['template_id'] for b in client.get('/api/bindings', headers=HEADERS).json()] == [1]
    third = client.post('/api/enrollments', headers=HEADERS, json={'device_id': 'office-01', 'employee_code': 'E001'}).json()
    assert third['template_id'] == 4


def test_inactive_employee_cannot_be_enrolled(client):
    client.post('/api/employees', headers=HEADERS, json={'code': 'E009', 'name': 'Former', 'active': False})
    assert client.post('/api/enrollments', headers=HEADERS, json={'device_id': 'office-01', 'employee_code': 'E009'}).status_code == 409


@pytest.fixture
def panel(tmp_path):
    app_client = TestClient(create_app(tmp_path / 'panel.sqlite3', ADMIN, {'office-01': DEVICE}, live_seconds=1))
    assert app_client.put('/api/admin/credentials', headers=HEADERS, json={'username': 'panel-admin', 'password': 'test-pass-1'}).status_code == 200
    return app_client


def test_login_session_grants_admin_access_and_logout_revokes_it(panel):
    assert panel.get('/api/me').status_code == 401
    assert panel.post('/api/login', json={'username': 'panel-admin', 'password': 'wrong'}).status_code == 401
    assert panel.post('/api/login', json={'username': 'nobody', 'password': 'test-pass-1'}).status_code == 401
    response = panel.post('/api/login', json={'username': 'panel-admin', 'password': 'test-pass-1'})
    assert response.status_code == 200
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert panel.get('/api/me').json()['username'] == 'panel-admin'
    assert panel.post('/api/employees', json={'code': 'E001', 'name': 'Test Staff'}).status_code == 200
    assert panel.post('/api/employees', headers={'Origin': 'https://evil.example'}, json={'code': 'E002', 'name': 'X'}).status_code == 403
    panel.post('/api/logout')
    assert panel.get('/api/employees').status_code == 401


def test_password_change_needs_current_password_and_signs_out(panel):
    panel.post('/api/login', json={'username': 'panel-admin', 'password': 'test-pass-1'})
    bad = panel.put('/api/admin/credentials', json={'username': 'panel-admin', 'password': 'longer-pass', 'current_password': 'nope'})
    assert bad.status_code == 403
    assert panel.put('/api/admin/credentials', json={'username': 'panel-admin', 'password': 'short'}).status_code == 422
    good = panel.put('/api/admin/credentials', json={'username': 'panel-admin', 'password': 'longer-pass', 'current_password': 'test-pass-1'})
    assert good.status_code == 200
    assert panel.get('/api/me').status_code == 401
    assert panel.post('/api/login', json={'username': 'panel-admin', 'password': 'test-pass-1'}).status_code == 401
    assert panel.post('/api/login', json={'username': 'panel-admin', 'password': 'longer-pass'}).status_code == 200


def test_repeated_wrong_passwords_are_throttled(panel):
    for _ in range(5):
        assert panel.post('/api/login', json={'username': 'panel-admin', 'password': 'guess'}).status_code == 401
    assert panel.post('/api/login', json={'username': 'panel-admin', 'password': 'test-pass-1'}).status_code == 429


def test_live_stream_sends_new_attendance_and_status(panel):
    client_events = []
    assign(panel)
    panel.post('/api/events', headers=DEVICE_HEADERS, json=event())
    panel.post('/api/login', json={'username': 'panel-admin', 'password': 'test-pass-1'})
    with panel.stream('GET', '/api/live?after=0') as response:
        assert response.headers['content-type'].startswith('text/event-stream')
        body = ''.join(response.iter_text())
    for block in body.split('\n\n'):
        lines = dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line)
        if 'event' in lines:
            client_events.append((lines['event'], json.loads(lines['data'])))
    kinds = [k for k, _ in client_events]
    assert kinds[0] == 'attendance' and 'status' in kinds
    assert client_events[0][1]['employee_code'] == 'E001' and client_events[0][1]['seq'] == 1
    with panel.stream('GET', '/api/live?after=1') as response:
        assert 'event: attendance' not in ''.join(response.iter_text())
    assert panel.get('/api/live').status_code == 200
    panel.post('/api/logout')
    assert panel.get('/api/live').status_code == 401
