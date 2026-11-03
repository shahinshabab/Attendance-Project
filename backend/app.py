"""Attendance API. Fingerprint images/templates never leave the sensor."""
import asyncio
import base64
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


class Employee(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r'^[A-Za-z0-9_-]+$')
    name: str = Field(min_length=1, max_length=100)
    active: bool = True


class Binding(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    template_id: int = Field(ge=1, le=1000)
    employee_code: str


class Event(BaseModel):
    event_id: str = Field(min_length=8, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    device_id: str = Field(min_length=1, max_length=64)
    template_id: int = Field(ge=1, le=1000)
    action: Literal['IN', 'OUT']
    occurred_at: datetime | None = None
    confidence: int = Field(ge=0, le=65535)
    uptime_ms: int = Field(ge=0)

    @field_validator('occurred_at')
    @classmethod
    def aware_time(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('occurred_at must include a timezone')
        return value.astimezone(timezone.utc) if value else None


class WifiConfig(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    password: str = Field(default='', max_length=63)

    @field_validator('ssid')
    @classmethod
    def ssid_bytes(cls, value):
        if len(value.encode()) > 32:
            raise ValueError('SSID is limited to 32 bytes')
        return value

    @field_validator('password')
    @classmethod
    def wpa_length(cls, value):
        if value and not 8 <= len(value.encode()) <= 63:
            raise ValueError('WPA password must be 8-63 characters, or empty for an open network')
        return value


class EnrollmentRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    employee_code: str


class DeviceReport(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    firmware: str = Field(default='', max_length=32)
    network: Literal['office', 'fallback', 'usb', 'offline'] = 'offline'
    ssid: str = Field(default='', max_length=32)
    rssi: int = Field(default=0, ge=-127, le=0)
    wifi_version: int = Field(default=0, ge=0)
    office_error: str = Field(default='', max_length=64)
    pending: int = Field(default=0, ge=0)
    sensor: bool = False
    templates: int = Field(default=0, ge=0, le=65535)
    capacity: int = Field(default=0, ge=0, le=65535)
    mode: Literal['IN', 'OUT'] = 'IN'
    clock_ok: bool = False
    uptime_ms: int = Field(default=0, ge=0)


class EnrollmentResult(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    success: bool
    message: str = Field(default='', max_length=200)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r'^[A-Za-z0-9_.-]+$')
    password: str = Field(min_length=6, max_length=256)
    current_password: str = Field(default='', max_length=256)


SESSION_COOKIE = 'attendance_session'
SESSION_HOURS = 12


def hash_password(password, iterations=310_000):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    return f'pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}'


def check_password(password, stored):
    try:
        scheme, iterations, salt, digest = stored.split('$')
        if scheme != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


class LoginLimiter:
    """Failed-login throttle: per client address, plus a global cap against distributed guessing."""

    def __init__(self, per_client=5, total=30, window=900):
        self.per_client, self.total, self.window = per_client, total, window
        self.failures = {}
        self.lock = threading.Lock()

    def _prune(self, now):
        for client in list(self.failures):
            self.failures[client] = [t for t in self.failures[client] if now - t < self.window]
            if not self.failures[client]:
                del self.failures[client]

    def blocked(self, client):
        with self.lock:
            now = time.monotonic()
            self._prune(now)
            return (len(self.failures.get(client, [])) >= self.per_client or
                    sum(len(v) for v in self.failures.values()) >= self.total)

    def failed(self, client):
        with self.lock:
            self.failures.setdefault(client, []).append(time.monotonic())

    def succeeded(self, client):
        with self.lock:
            self.failures.pop(client, None)


def create_app(database_path=None, admin_key=None, device_keys=None, live_seconds=300):
    load_env()
    db_path = Path(database_path or os.getenv('DATABASE_PATH', ROOT / 'data/attendance.sqlite3'))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    admin = admin_key or os.getenv('ADMIN_API_KEY', '')
    devices = device_keys if device_keys is not None else json.loads(os.getenv('DEVICE_KEYS_JSON', '{}'))
    if len(admin) < 24 or not devices or any(len(v) < 24 or v == admin for v in devices.values()):
        raise RuntimeError('Configure separate admin/device keys (24+ characters). Run scripts/setup.ps1.')
    office_zone = ZoneInfo(os.getenv('ATTENDANCE_TIMEZONE', 'Asia/Kolkata'))

    @contextmanager
    def connection():
        db = sqlite3.connect(db_path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS employees (
              code TEXT PRIMARY KEY, name TEXT NOT NULL, active INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS bindings (
              device_id TEXT NOT NULL, template_id INTEGER NOT NULL,
              employee_code TEXT NOT NULL REFERENCES employees(code),
              PRIMARY KEY(device_id, template_id));
            CREATE TABLE IF NOT EXISTS events (
              event_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, template_id INTEGER NOT NULL,
              employee_code TEXT REFERENCES employees(code), action TEXT NOT NULL,
              occurred_at TEXT, received_at TEXT NOT NULL, confidence INTEGER NOT NULL,
              uptime_ms INTEGER NOT NULL, payload_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS events_time ON events(received_at);
            CREATE TABLE IF NOT EXISTS device_wifi (
              device_id TEXT PRIMARY KEY, ssid TEXT NOT NULL, password TEXT NOT NULL,
              version INTEGER NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS device_status (
              device_id TEXT PRIMARY KEY, last_seen TEXT NOT NULL, report TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS enrollments (
              id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, template_id INTEGER NOT NULL,
              employee_code TEXT NOT NULL REFERENCES employees(code), status TEXT NOT NULL,
              message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(device_id, template_id));
            CREATE TABLE IF NOT EXISTS admins (
              username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires_at TEXT NOT NULL);
        ''')

    app = FastAPI(title='Office fingerprint attendance', version='0.1.0')

    limiter = LoginLimiter()
    dummy_hash = hash_password(secrets.token_urlsafe(16))

    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def session_user(token):
        if not token:
            return None
        with connection() as db:
            row = db.execute('SELECT username, expires_at FROM sessions WHERE token_hash=?', (token_hash(token),)).fetchone()
        if row and datetime.fromisoformat(row['expires_at']) > datetime.now(timezone.utc):
            return row['username']
        return None

    def require_admin(request: Request, x_api_key: str = Header(default='')):
        """Admin API key (tools) or a logged-in dashboard session. Returns who is acting."""
        if x_api_key and hmac.compare_digest(x_api_key.encode(), admin.encode()):
            return {'via': 'key', 'username': None}
        username = session_user(request.cookies.get(SESSION_COOKIE))
        if not username:
            raise HTTPException(401, 'Login required')
        # Cookies are SameSite=Strict; also refuse a cross-origin browser write as defense in depth.
        origin = request.headers.get('origin')
        if request.method not in ('GET', 'HEAD') and origin and urlparse(origin).netloc != request.headers.get('host'):
            raise HTTPException(403, 'Cross-origin request refused')
        return {'via': 'session', 'username': username}

    def client_address(request):
        return request.client.host if request.client else 'unknown'

    @app.post('/api/login')
    def login(credentials: Login, request: Request, response: Response):
        client = client_address(request)
        if limiter.blocked(client):
            raise HTTPException(429, 'Too many failed logins. Wait 15 minutes and try again.')
        with connection() as db:
            row = db.execute('SELECT password_hash FROM admins WHERE username=?', (credentials.username,)).fetchone()
        # Hash even for an unknown user so timing does not reveal valid usernames.
        if not check_password(credentials.password, row['password_hash'] if row else dummy_hash) or not row:
            limiter.failed(client)
            raise HTTPException(401, 'Wrong username or password')
        limiter.succeeded(client)
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
        with connection() as db:
            db.execute('DELETE FROM sessions WHERE expires_at < ?', (datetime.now(timezone.utc).isoformat(),))
            db.execute('INSERT INTO sessions VALUES (?, ?, ?)', (token_hash(token), credentials.username, expires.isoformat()))
        response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_HOURS * 3600, httponly=True,
                            secure=request.url.scheme == 'https', samesite='strict', path='/')
        return {'username': credentials.username}

    @app.post('/api/logout')
    def logout(request: Request, response: Response):
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            with connection() as db:
                db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(token),))
        response.delete_cookie(SESSION_COOKIE, path='/')
        return {'status': 'logged out'}

    @app.get('/api/me')
    def me(who=Depends(require_admin)):
        with connection() as db:
            last_seq = db.execute('SELECT COALESCE(MAX(rowid), 0) FROM events').fetchone()[0]
        return {'username': who['username'], 'office_date': datetime.now(office_zone).date().isoformat(),
                'server_time': datetime.now(timezone.utc).isoformat(), 'last_seq': last_seq}

    @app.put('/api/admin/credentials')
    def set_credentials(credentials: Credentials, who=Depends(require_admin)):
        now = datetime.now(timezone.utc).isoformat()
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if who['via'] == 'session':
                row = db.execute('SELECT password_hash FROM admins WHERE username=?', (who['username'],)).fetchone()
                if not row or not check_password(credentials.current_password, row['password_hash']):
                    raise HTTPException(403, 'Current password is wrong')
            # Single admin login: replacing it signs every existing session out.
            db.execute('DELETE FROM admins')
            db.execute('DELETE FROM sessions')
            db.execute('INSERT INTO admins VALUES (?, ?, ?)', (credentials.username, hash_password(credentials.password), now))
        return {'username': credentials.username, 'status': 'saved; please log in again'}

    @app.get('/', include_in_schema=False)
    def dashboard():
        return FileResponse(ROOT / 'backend/static/index.html', headers={'Cache-Control': 'no-store'})

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.get('/api/employees', dependencies=[Depends(require_admin)])
    def employees():
        with connection() as db:
            return [dict(r) for r in db.execute('SELECT * FROM employees ORDER BY code')]

    @app.post('/api/employees', dependencies=[Depends(require_admin)])
    def save_employee(employee: Employee):
        with connection() as db:
            db.execute('INSERT INTO employees VALUES (?, ?, ?) ON CONFLICT(code) DO UPDATE SET name=excluded.name, active=excluded.active',
                       (employee.code, employee.name, int(employee.active)))
        return employee

    @app.get('/api/bindings', dependencies=[Depends(require_admin)])
    def bindings():
        with connection() as db:
            return [dict(r) for r in db.execute('SELECT * FROM bindings ORDER BY device_id, template_id')]

    @app.post('/api/bindings', dependencies=[Depends(require_admin)])
    def bind(binding: Binding):
        if binding.device_id not in devices:
            raise HTTPException(400, 'Unknown configured device')
        with connection() as db:
            if not db.execute('SELECT 1 FROM employees WHERE code=?', (binding.employee_code,)).fetchone():
                raise HTTPException(404, 'Create the employee first')
            old = db.execute('SELECT employee_code FROM bindings WHERE device_id=? AND template_id=?',
                             (binding.device_id, binding.template_id)).fetchone()
            if old and old[0] != binding.employee_code:
                raise HTTPException(409, 'Slot already assigned. Use a fresh slot; historical/offline events must not be reassigned.')
            db.execute('INSERT OR IGNORE INTO bindings VALUES (?, ?, ?)',
                       (binding.device_id, binding.template_id, binding.employee_code))
        return binding

    def require_device(device_id, key):
        expected = devices.get(device_id)
        if not expected or not hmac.compare_digest(key.encode(), expected.encode()):
            raise HTTPException(401, 'Invalid device credentials')

    def known_device(device_id):
        if device_id not in devices:
            raise HTTPException(400, 'Unknown configured device')

    @app.get('/api/devices', dependencies=[Depends(require_admin)])
    def device_list():
        with connection() as db:
            status = {r['device_id']: r for r in db.execute('SELECT * FROM device_status')}
            wifi = {r['device_id']: r for r in db.execute('SELECT device_id, ssid, version, updated_at FROM device_wifi')}
        result = []
        for device_id in sorted(devices):
            row, config = status.get(device_id), wifi.get(device_id)
            result.append({'device_id': device_id,
                           'last_seen': row['last_seen'] if row else None,
                           'report': json.loads(row['report']) if row else None,
                           'wifi': dict(config) if config else None})
        return result

    @app.put('/api/devices/{device_id}/wifi', dependencies=[Depends(require_admin)])
    def set_wifi(device_id: str, config: WifiConfig):
        known_device(device_id)
        now = datetime.now(timezone.utc).isoformat()
        with connection() as db:
            db.execute('''INSERT INTO device_wifi VALUES (?, ?, ?, 1, ?) ON CONFLICT(device_id) DO UPDATE SET
                          ssid=excluded.ssid, password=excluded.password, version=version + 1, updated_at=excluded.updated_at''',
                       (device_id, config.ssid, config.password, now))
            version = db.execute('SELECT version FROM device_wifi WHERE device_id=?', (device_id,)).fetchone()[0]
        # The password is write-only through the admin API; only the device receives it.
        return {'device_id': device_id, 'ssid': config.ssid, 'version': version}

    def enrollment_rows(db, where='', params=(), limit=50):
        return [dict(r) for r in db.execute(f'''SELECT n.*, p.name FROM enrollments n
            LEFT JOIN employees p ON p.code=n.employee_code {where} ORDER BY n.id DESC LIMIT ?''', (*params, limit))]

    @app.get('/api/enrollments', dependencies=[Depends(require_admin)])
    def enrollments(limit: int = 50):
        with connection() as db:
            return enrollment_rows(db, limit=max(1, min(limit, 1000)))

    @app.post('/api/enrollments', dependencies=[Depends(require_admin)])
    def request_enrollment(request: EnrollmentRequest):
        known_device(request.device_id)
        now = datetime.now(timezone.utc).isoformat()
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            employee = db.execute('SELECT active FROM employees WHERE code=?', (request.employee_code,)).fetchone()
            if not employee:
                raise HTTPException(404, 'Create the employee first')
            if not employee[0]:
                raise HTTPException(409, 'Employee is inactive')
            if db.execute("SELECT 1 FROM enrollments WHERE device_id=? AND status IN ('pending', 'active')",
                          (request.device_id,)).fetchone():
                raise HTTPException(409, 'This scanner already has an enrollment waiting; finish or cancel it first')
            # Never reuse a slot that was ever bound or attempted, so history cannot move between staff.
            used = db.execute('''SELECT MAX(t) FROM (SELECT template_id t FROM bindings WHERE device_id=?
                                 UNION ALL SELECT template_id FROM enrollments WHERE device_id=?)''',
                              (request.device_id, request.device_id)).fetchone()[0] or 0
            if used >= 999:
                raise HTTPException(409, 'No unused sensor slots remain on this scanner')
            cursor = db.execute("INSERT INTO enrollments (device_id, template_id, employee_code, status, created_at, updated_at) "
                                "VALUES (?, ?, ?, 'pending', ?, ?)", (request.device_id, used + 1, request.employee_code, now, now))
            return enrollment_rows(db, 'WHERE n.id=?', (cursor.lastrowid,))[0]

    @app.post('/api/enrollments/{enrollment_id}/cancel', dependencies=[Depends(require_admin)])
    def cancel_enrollment(enrollment_id: int):
        with connection() as db:
            changed = db.execute("UPDATE enrollments SET status='cancelled', message='Cancelled from dashboard', updated_at=? "
                                 "WHERE id=? AND status IN ('pending', 'active')",
                                 (datetime.now(timezone.utc).isoformat(), enrollment_id)).rowcount
            if not changed:
                raise HTTPException(409, 'This enrollment has already finished')
            return enrollment_rows(db, 'WHERE n.id=?', (enrollment_id,))[0]

    @app.post('/api/device/sync')
    def device_sync(report: DeviceReport, x_api_key: str = Header(default='')):
        require_device(report.device_id, x_api_key)
        now = datetime.now(timezone.utc)
        reply = {'server_time': int(now.timestamp())}
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO device_status VALUES (?, ?, ?) ON CONFLICT(device_id) DO UPDATE SET '
                       'last_seen=excluded.last_seen, report=excluded.report',
                       (report.device_id, now.isoformat(), report.model_dump_json()))
            wifi = db.execute('SELECT ssid, password, version FROM device_wifi WHERE device_id=?', (report.device_id,)).fetchone()
            if wifi and wifi['version'] != report.wifi_version:
                reply['wifi'] = dict(wifi)
            # An 'active' command is re-sent until the device reports a result, e.g. after a reboot mid-enrollment.
            command = db.execute('''SELECT n.id, n.template_id, n.employee_code, p.name FROM enrollments n
                JOIN employees p ON p.code=n.employee_code WHERE n.device_id=? AND n.status IN ('pending', 'active')
                ORDER BY n.id LIMIT 1''', (report.device_id,)).fetchone()
            if command:
                db.execute("UPDATE enrollments SET status='active', updated_at=? WHERE id=?", (now.isoformat(), command['id']))
                reply['command'] = {'id': command['id'], 'type': 'enroll', 'slot': command['template_id'],
                                    'employee_code': command['employee_code'], 'employee_name': command['name']}
        return reply

    @app.post('/api/device/enrollments/{enrollment_id}/result')
    def enrollment_result(enrollment_id: int, result: EnrollmentResult, x_api_key: str = Header(default='')):
        require_device(result.device_id, x_api_key)
        now = datetime.now(timezone.utc).isoformat()
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM enrollments WHERE id=? AND device_id=?', (enrollment_id, result.device_id)).fetchone()
            if not row:
                raise HTTPException(404, 'Unknown enrollment for this device')
            if row['status'] == 'cancelled' and result.success and row['message'] == 'Cancelled from dashboard':
                db.execute('UPDATE enrollments SET message=?, updated_at=? WHERE id=?',
                           ('Cancelled; finger was stored on the scanner but the slot is left unassigned', now, enrollment_id))
            if row['status'] != 'active':
                return {'id': enrollment_id, 'status': row['status']}  # repeated report after a lost reply
            status, message = ('enrolled', result.message) if result.success else ('failed', result.message)
            if result.success:
                old = db.execute('SELECT employee_code FROM bindings WHERE device_id=? AND template_id=?',
                                 (row['device_id'], row['template_id'])).fetchone()
                if old and old[0] != row['employee_code']:
                    status, message = 'failed', 'Slot already assigned to another employee; template left unassigned'
                else:
                    db.execute('INSERT OR IGNORE INTO bindings VALUES (?, ?, ?)',
                               (row['device_id'], row['template_id'], row['employee_code']))
            db.execute('UPDATE enrollments SET status=?, message=?, updated_at=? WHERE id=?', (status, message, now, enrollment_id))
        return {'id': enrollment_id, 'status': status}

    @app.post('/api/events')
    def ingest(event: Event, x_api_key: str = Header(default='')):
        require_device(event.device_id, x_api_key)
        payload_hash = hashlib.sha256(event.model_dump_json().encode()).hexdigest()
        now = datetime.now(timezone.utc)
        if event.occurred_at and (event.occurred_at - now).total_seconds() > 300:
            raise HTTPException(422, 'Device clock is in the future')
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT payload_hash FROM events WHERE event_id=?', (event.event_id,)).fetchone()
            if old:
                if old[0] != payload_hash:
                    raise HTTPException(409, 'Event ID reused with different data')
                return {'event_id': event.event_id, 'status': 'duplicate'}
            binding = db.execute('SELECT employee_code FROM bindings WHERE device_id=? AND template_id=?',
                                 (event.device_id, event.template_id)).fetchone()
            db.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (event.event_id, event.device_id, event.template_id, binding[0] if binding else None,
                        event.action, event.occurred_at.isoformat() if event.occurred_at else None,
                        now.isoformat(), event.confidence, event.uptime_ms, payload_hash))
        return {'event_id': event.event_id, 'status': 'recorded' if binding else 'unmapped'}

    ROW_SQL = '''SELECT e.rowid AS seq, e.event_id, e.device_id, e.template_id, e.employee_code,
        p.name, p.active, e.action, e.occurred_at, e.received_at, e.confidence
        FROM events e LEFT JOIN employees p ON p.code=e.employee_code'''

    def present(row):
        item = dict(row)
        stamp = datetime.fromisoformat(item['occurred_at'] or item['received_at']).astimezone(office_zone)
        item['local_time'] = stamp.isoformat()
        item['time_source'] = 'device' if item['occurred_at'] else 'received_only'
        return item, stamp

    def records(day: str | None, limit: int):
        target = None
        if day:
            try:
                target = datetime.strptime(day, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(422, 'Use YYYY-MM-DD')
        with connection() as db:
            rows = db.execute(ROW_SQL + ' ORDER BY COALESCE(e.occurred_at, e.received_at) DESC')
            result = []
            for row in rows:
                item, stamp = present(row)
                if target and stamp.date() != target:
                    continue
                result.append(item)
                if len(result) >= limit:
                    break
            return result

    @app.get('/api/attendance', dependencies=[Depends(require_admin)])
    def attendance(day: str | None = None, limit: int = 500):
        return records(day, max(1, min(limit, 10000)))

    @app.get('/api/export.csv', dependencies=[Depends(require_admin)])
    def export(day: str | None = None):
        rows = records(day, 100000)
        fields = ['event_id', 'employee_code', 'name', 'active', 'action', 'local_time', 'time_source', 'device_id', 'template_id', 'occurred_at', 'received_at', 'confidence']
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            # Spreadsheet formula injection protection for employee names/codes.
            writer.writerow({k: ("'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v) for k, v in row.items()})
        return Response(stream.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="attendance.csv"'})

    def rows_after(seq):
        with connection() as db:
            return [present(row)[0] for row in db.execute(ROW_SQL + ' WHERE e.rowid > ? ORDER BY e.rowid LIMIT 200', (seq,))]

    @app.get('/api/live')
    async def live(request: Request, after: int = 0, who=Depends(require_admin)):
        """Server-sent events: new attendance rows as they arrive, plus scanner status every 5 seconds."""
        resume = request.headers.get('last-event-id', '')
        seq = max(after, int(resume) if resume.isdigit() else 0)
        token = request.cookies.get(SESSION_COOKIE)

        def message(kind, data, event_id=None):
            return (f'id: {event_id}\n' if event_id is not None else '') + f'event: {kind}\ndata: {json.dumps(data)}\n\n'

        async def stream():
            nonlocal seq
            yield 'retry: 3000\n\n'
            deadline = time.monotonic() + live_seconds  # the browser reconnects; keeps restarts and stale sessions short
            next_status = 0.0
            while time.monotonic() < deadline and not await request.is_disconnected():
                for row in await asyncio.to_thread(rows_after, seq):
                    seq = row['seq']
                    yield message('attendance', row, seq)
                if time.monotonic() >= next_status:
                    if who['via'] == 'session' and not await asyncio.to_thread(session_user, token):
                        yield message('logout', {})
                        return
                    status = {'devices': await asyncio.to_thread(device_list),
                              'office_date': datetime.now(office_zone).date().isoformat(),
                              'server_time': datetime.now(timezone.utc).isoformat()}
                    yield message('status', status)
                    next_status = time.monotonic() + 5
                await asyncio.sleep(1)

        return StreamingResponse(stream(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    return app
