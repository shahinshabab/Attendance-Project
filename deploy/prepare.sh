set -eu
sudo -n true
if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-venv
fi
if ! id attendance >/dev/null 2>&1; then
    sudo useradd --system --user-group --home-dir /var/lib/attendance --shell /usr/sbin/nologin attendance
fi
sudo install -d -m 755 -o root -g root /opt/attendance /opt/attendance/releases
sudo install -d -m 750 -o root -g attendance /etc/attendance
sudo install -d -m 750 -o attendance -g attendance /var/lib/attendance
if [ ! -x /opt/attendance/venv/bin/python ]; then
    sudo python3 -m venv /opt/attendance/venv
fi
printf 'Attendance runtime directories and Python environment are ready.\n'
