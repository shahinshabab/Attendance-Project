set -eu
release=$(readlink -f /opt/attendance/current)
case "$release" in
    /opt/attendance/releases/*) ;;
    *) printf 'Unexpected active release path\n' >&2; exit 1 ;;
esac
sudo find "$release" -type d -exec chmod 755 {} +
sudo find "$release" -type f -exec chmod 644 {} +
sudo stat -c '%U:%G %a %n' "$release/backend/app.py" /etc/attendance/attendance.env /var/lib/attendance
systemctl is-active attendance.service
systemctl is-enabled attendance.service
systemctl show attendance.service --property=MemoryCurrent --property=User --property=Restart
ss -lnt
if command -v caddy >/dev/null 2>&1; then
    caddy version
    systemctl is-active caddy.service
    sudo journalctl -u caddy.service -n 20 --no-pager
fi
