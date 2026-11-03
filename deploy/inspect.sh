set -eu
id
for instruction in /AGENTS.md /opt/AGENTS.md /opt/attendance/AGENTS.md "$HOME/AGENTS.md"; do
    if [ -f "$instruction" ]; then cat "$instruction"; fi
done
python3 --version
dpkg-query -W python3-venv python3.12-venv 2>/dev/null || true
sudo -n true
systemctl --version | head -n 1
if [ -e /opt/attendance ]; then ls -ld /opt/attendance; fi
if systemctl cat attendance.service >/dev/null 2>&1; then systemctl cat attendance.service; fi
ss -lnt
