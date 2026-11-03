# Attendance-Server deployment record

The SSH alias `Attendance-Server` connects as `ubuntu`. Inspection confirmed Ubuntu 24.04 on x86-64, about 1 GB RAM, sufficient disk space, passwordless sudo, and no existing web service. `attendance.shahinanalytics.com` resolves to the configured server's IP address.

Prepared deployment:

1. Install Python virtual-environment support and create the dedicated `attendance` service account.
2. Transfer the app and this project's generated admin/device keys over SSH. Keep keys in `/etc/attendance/attendance.env`, readable only by root and the service group. This allows the existing USB bridge configuration to authenticate to the server.
3. Install pinned Python runtime dependencies in `/opt/attendance/venv`; store versioned code in `/opt/attendance/releases/` and attendance data in `/var/lib/attendance/attendance.sqlite3`.
4. Run candidate tests against a temporary database before switching the active release. Enable `attendance.service`, running one worker as the dedicated user on server localhost port 8000.
5. Install Caddy from its official package repository and add a configuration specifically for `attendance.shahinanalytics.com`. Preserve the existing main Caddy configuration and add an import. Enable HTTPS certificate provisioning/renewal and reverse-proxy requests to the attendance service.
6. Check service health, authentication, and the public HTTPS URL. Only the temporary preflight database receives synthetic attendance; live checks do not insert staff or scans.

Both app and proxy start automatically after server reboot. Public certificate issuance requires the server to be reachable on TCP 80 and 443. Cloud firewall/security-group changes are not included in these scripts. SSH itself stays on its current port and configuration.

Prepared files: `deploy/attendance.service`, `deploy/Caddyfile`, `deploy/prepare.sh`, `deploy/https.sh`, and `deploy/check_service.py`.

After approval, the activation command is:

```powershell
.\.venv\Scripts\python.exe -m tools.deploy --config "$env:USERPROFILE\.ssh\config" --activate --domain attendance.shahinanalytics.com
```

The app will be at `https://attendance.shahinanalytics.com`. The USB bridge can use:

```powershell
.\scripts\device.ps1 bridge -Port COM3 -Server https://attendance.shahinanalytics.com
```

For SSH-only access, `scripts/start-tunnel.ps1` forwards local port 8765 to the server's app port. Do not run a local development server on that same local port while the tunnel is active.

Deployment was explicitly approved and completed on **2026-10-28**. Active release: `20261028T154754Z-a5664d`. The app and Caddy are active and enabled at boot. Public HTTPS, certificate trust, dashboard loading, API authentication, and HTTP-to-HTTPS redirection passed checks. Candidate staff/attendance/retry tests used a temporary database, with no synthetic attendance written to the live database. Server source permissions were normalized to root-owned 644 files and 755 directories; the credential file is root:attendance 640.

Automatic approval review initially blocked installation/key transfer, and execution proceeded only after the user explicitly approved both. The original local Windows port-8000 forwarding rule remains unchanged; server port 8000 is a separate localhost-only listener.

Configuration references: [systemd execution settings](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html), [Caddy installation](https://caddyserver.com/docs/install), [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).
