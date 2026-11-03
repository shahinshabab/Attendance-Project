# API reference

Local service: `http://127.0.0.1:8765`. Interactive schema is available at `/docs` when the server is running. Device and admin API keys are different. Use `X-API-Key` on all endpoints below except health.

| Method | Path | Key | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | None | Health only |
| GET | `/api/employees` | Admin | List staff |
| POST | `/api/employees` | Admin | Add/update code, name, active flag |
| GET | `/api/bindings` | Admin | List sensor-slot assignments |
| POST | `/api/bindings` | Admin | Assign a fresh device/slot to staff |
| POST | `/api/events` | Device | Accept an identified-finger scan |
| GET | `/api/attendance?day=YYYY-MM-DD&limit=500` | Admin | Office-local date filter; date optional |
| GET | `/api/export.csv?day=YYYY-MM-DD` | Admin | CSV download; date optional |
| GET | `/api/devices` | Admin | Scanner status from its last check-in, and its office Wi-Fi (no password) |
| PUT | `/api/devices/{device_id}/wifi` | Admin | Save office Wi-Fi `{"ssid","password"}`; bumps the version the scanner applies |
| GET | `/api/enrollments` | Admin | Recent server-requested enrollments and their status |
| POST | `/api/enrollments` | Admin | `{"device_id","employee_code"}`: allocate a never-used slot and queue an enrollment |
| POST | `/api/enrollments/{id}/cancel` | Admin | Cancel a waiting or in-progress enrollment |
| POST | `/api/device/sync` | Device | Scanner check-in: status report in; Wi-Fi update and/or enrollment command out |
| POST | `/api/device/enrollments/{id}/result` | Device | `{"device_id","success","message"}`; success binds the slot to the employee |

Staff example:

```json
{"code":"EMP001","name":"Example Staff","active":true}
```

Binding example (also requires that the device ID is configured in `DEVICE_KEYS_JSON`):

```json
{"device_id":"office-01","template_id":1,"employee_code":"EMP001"}
```

Event example:

```json
{
  "event_id": "a1b2c3d40000111122223333",
  "device_id": "office-01",
  "template_id": 1,
  "action": "IN",
  "occurred_at": "2026-10-28T03:30:00Z",
  "confidence": 120,
  "uptime_ms": 45000
}
```

Set `occurred_at` to null if the device has no valid clock. Never send a guessed local timestamp. Valid timestamps include a timezone and are normalized to UTC; timestamps more than five minutes ahead of the server are rejected.

A successful response contains the exact submitted `event_id` and one of `recorded`, `duplicate`, or `unmapped`. All three mean the event is safely accepted and can be acknowledged to the device. `unmapped` records need human review; they are retained instead of silently discarded. A reused event ID with different normalized content returns 409 and must not be acknowledged.

## Scanner check-in (Wi-Fi mode)

The scanner calls `POST /api/device/sync` about every 10 seconds with its status (network, signal, applied `wifi_version`, queue size, sensor state). The reply always has `server_time` (Unix seconds; sets the clock when NTP is blocked) and may include:

```json
{"server_time": 1793158200,
 "wifi": {"ssid": "Office", "password": "...", "version": 3},
 "command": {"id": 7, "type": "enroll", "slot": 2, "employee_code": "EMP001", "employee_name": "Shabab"}}
```

`wifi` is sent only while the scanner's applied version differs. It saves it to flash and reconnects. Enrollment status goes `pending` → `active` (sent to the scanner; re-sent after a reboot until a result arrives) → `enrolled` / `failed` / `cancelled`. Slots are allocated above every slot ever bound or attempted on that scanner, so a slot is never reused for a different person. The scanner stores its result in flash before reporting it, and does not take new work until the server has received it.

## USB protocol

Baud rate: 115200, newline-delimited UTF-8. Sensor UART is separate and defaults to 57600 baud. Commands:

```text
STATUS
TIME 1793158200
IN
OUT
ENROLL 1
DELETE 1
ACK a1b2c3d40000111122223333
```

`TIME` is Unix seconds in UTC; the example is illustrative. The bridge sends the current computer time automatically. `ENROLL` and `DELETE` operate on the physical sensor only. Enrollment does not update the server assignment.

In USB mode the device repeats a packet such as `{"type":"attendance","event":{...}}` until the bridge receives server acceptance and sends `ACK <event_id>`. Status lines use `{"type":"status","message":"..."}`. ACK only removes the current queue head if its ID matches exactly. Wi-Fi mode uses the same event object over HTTPS and ignores serial ACK commands.
