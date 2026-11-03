# Server connection and deployment

The app is deployed at **https://attendance.shahinanalytics.com** on the Ubuntu 24.04 server reached through SSH alias `Attendance-Server`. The deployment and key transfer were explicitly approved. The app runs as `attendance.service`, behind Caddy HTTPS, with automatic startup enabled. See [the deployment record](DEPLOYMENT-PLAN.md). Both USB forwarding and direct ESP32 Wi-Fi can target the same API.

Open the public dashboard and use the `ADMIN_API_KEY` value in this computer's ignored `.env` file. Never use that admin key in the firmware. For the USB bridge, use `scripts/device.ps1 bridge -Port COM3 -Server https://attendance.shahinanalytics.com` after the hardware is wired and firmware uploaded.

Useful server checks:

```sh
ssh Attendance-Server
sudo systemctl status attendance caddy
sudo journalctl -u attendance -n 50 --no-pager
```

Server code is under `/opt/attendance/current`; the database is `/var/lib/attendance/attendance.sqlite3`; protected credentials are `/etc/attendance/attendance.env`. No cloud firewall rules or local Windows port-forwarding rules were changed. Public ports 80 and 443 were already reachable, and the trusted HTTPS certificate was successfully issued.

## Local Windows server

Run `scripts/start-server.ps1` and keep it running. It binds to `127.0.0.1:8765` by default, so only this computer can access it. Use the USB bridge initially. Do not open Windows firewall ports or router port forwarding for this local workflow. Container deployments use port 8000 internally.

`GET /health` is public and reports only service health. `/api/*` attendance and staff data require an API key. The dashboard loads without a key, and requires the admin key to load any records. Keys are submitted in the `X-API-Key` header, not the URL.

## Internet server preparation

The included Docker/Compose setup is suitable as a starting point on a Linux host with Docker Compose:

1. Copy the source and a server-specific `.env` securely. Preserve the device key used by an existing scanner/USB bridge. Do not copy `.venv`, build output, or unneeded local attendance data.
2. Run `docker compose up -d --build`. The application port is bound only to server localhost. The named `attendance-data` volume holds SQLite data. **Do not remove that volume.**
3. Put your existing HTTPS reverse proxy in front of `127.0.0.1:8000` and configure a domain and trusted certificate. Proxy the entire app, including `/api/events`, with no redirects on the configured ESP32 URL. Configure request/body limits and rate limits appropriate to a single small scanner. The actual proxy configuration will be matched to your server when details are supplied.
4. Test `https://YOUR_DOMAIN/health`, then test the dashboard with the admin key, and finally an enrollment/attendance round trip using a dedicated test staff member.
5. Back up SQLite using its online backup API or stop the service for a file copy. A live copy of only the main `.sqlite3` file can miss WAL transactions. Use a single app instance/writer with a local disk/volume; this starter is not a multi-server database architecture.

SQLite records staff, slot bindings, and accepted scan metadata. Fingerprint images/templates are not uploaded. Access control is a shared admin key in this starter; separate staff roles, password login, leave management, payroll, shift rules, and edit/audit workflows are future features.

## Direct Wi-Fi firmware configuration

Generate the ignored `firmware/include/config.h` instead of editing it by hand:

```powershell
.\.venv\Scripts\python.exe -m tools.firmware_config --server https://attendance.shahinanalytics.com --show-fallback
.\scripts\device.ps1 build
.\scripts\device.ps1 upload -Port COM3
```

It enables Wi-Fi mode and fills in the device key from `.env`, the server URL, and the Let's Encrypt/ZeroSSL root certificates from `certifi`. It keeps an existing fallback hotspot name/password, or generates a password on first run (`--fallback-ssid` / `--fallback-password` to choose your own). The office Wi-Fi is **not** compiled in; set it from the dashboard. The firmware verifies HTTPS, gets UTC from NTP or from the server's check-in reply, and keeps its queue if Wi-Fi, TLS, or the server fails. Do not disable certificate verification.

## Configuration reference

| Variable | Purpose |
| --- | --- |
| `ADMIN_API_KEY` | Independent, random secret used by dashboard/admin endpoints |
| `DEVICE_KEYS_JSON` | JSON object mapping device IDs to independent random secrets |
| `DATABASE_PATH` | SQLite file; local default `data/attendance.sqlite3` |
| `ATTENDANCE_TIMEZONE` | Display/report timezone, default `Asia/Kolkata` |

Restart the server after configuration changes. Use unique device IDs and keys for additional scanners; each scanner's sensor slot mapping is separate. Templates are not synchronized between sensors.
