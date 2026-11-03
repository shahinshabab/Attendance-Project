"""Package and deploy this attendance app to the configured SSH server."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tarfile

from backend.app import load_env

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='Attendance-Server')
    parser.add_argument('--config', default=str(Path.home() / '.ssh/config'))
    parser.add_argument('--activate', action='store_true', help='Install and start the tested candidate service')
    parser.add_argument('--package-only', action='store_true', help='Build the local deployment package without connecting or transferring secrets')
    parser.add_argument('--domain', help='Configure Caddy HTTPS for this domain when activating')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', args.host):
        parser.error('Use a simple SSH host alias')
    if args.domain and not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', args.domain):
        parser.error('Use a lowercase DNS hostname')
    load_env()
    admin = os.environ.get('ADMIN_API_KEY', '')
    device_keys = json.loads(os.environ.get('DEVICE_KEYS_JSON', '{}'))
    if len(admin) < 24 or not device_keys:
        raise RuntimeError('Run project setup first')
    release = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    local_stage = ROOT / 'data/deploy' / release
    local_stage.mkdir(parents=True)
    archive = local_stage / 'attendance.tar.gz'
    def archive_permissions(info):
        info.mode = 0o755 if info.isdir() else 0o644
        info.uid = info.gid = 0
        info.uname = info.gname = 'root'
        return info
    with tarfile.open(archive, 'w:gz') as tar:
        for directory in ('backend', 'deploy'):
            for path in sorted((ROOT / directory).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    tar.add(path, arcname=path.relative_to(ROOT).as_posix(), filter=archive_permissions)
        tar.add(ROOT / 'requirements-server-lock.txt', arcname='requirements-server-lock.txt', filter=archive_permissions)
    config = local_stage / 'attendance.env'
    config.write_text('ADMIN_API_KEY=' + admin + '\nDEVICE_KEYS_JSON=' + json.dumps(device_keys) +
                      '\nDATABASE_PATH=/var/lib/attendance/attendance.sqlite3\nATTENDANCE_TIMEZONE=' +
                      os.getenv('ATTENDANCE_TIMEZONE', 'Asia/Kolkata') + '\n', encoding='utf-8')
    if args.package_only:
        print(json.dumps({'release': release, 'archive': str(archive), 'domain': args.domain,
                          'status': 'packaged locally; no server connection or credential transfer'}, indent=2))
        return
    ssh_dir = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/OpenSSH'
    ssh = str(ssh_dir / 'ssh.exe') if os.name == 'nt' else 'ssh'
    scp = str(ssh_dir / 'scp.exe') if os.name == 'nt' else 'scp'
    common = ['-F', args.config, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15']

    def run_script(script):
        subprocess.run([ssh, *common, args.host, 'sh -s'], input=script.replace('\r\n', '\n').encode('utf-8'), check=True)

    stage = 'attendance-stage-' + release
    run_script('set -eu\numask 077\nmkdir "$HOME/' + stage + '"\n')
    subprocess.run([scp, *common, str(archive), str(config), args.host + ':' + stage + '/'], check=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    candidate = '/opt/attendance/releases/' + release
    prepare = (ROOT / 'deploy/prepare.sh').read_text(encoding='utf-8')
    script = 'set -eu\n' + prepare + f'''
stage="$HOME/{stage}"
printf '%s  %s\n' '{digest}' "$stage/attendance.tar.gz" | sha256sum -c -
sudo install -d -m 755 -o root -g root '{candidate}'
sudo tar --no-same-owner -xzf "$stage/attendance.tar.gz" -C '{candidate}'
sudo find '{candidate}' -type d -exec chmod 755 {{}} +
sudo find '{candidate}' -type f -exec chmod 644 {{}} +
if sudo test -e /etc/attendance/attendance.env; then
    if ! sudo cmp -s "$stage/attendance.env" /etc/attendance/attendance.env; then
        printf 'Existing server configuration differs. Refusing to replace credentials.\n' >&2
        exit 1
    fi
else
    sudo install -m 640 -o root -g attendance "$stage/attendance.env" /etc/attendance/attendance.env
fi
sudo ln -s /etc/attendance/attendance.env '{candidate}/.env'
sudo /opt/attendance/venv/bin/python -m pip install --disable-pip-version-check -r '{candidate}/requirements-server-lock.txt'
sudo -u attendance env PYTHONDONTWRITEBYTECODE=1 /opt/attendance/venv/bin/python '{candidate}/deploy/check_service.py'
sudo systemd-analyze verify '{candidate}/deploy/attendance.service'
'''
    if args.activate:
        script += f'''
if [ -e /opt/attendance/current ] && [ ! -L /opt/attendance/current ]; then
    printf 'Current release path is not a symlink; refusing replacement.\n' >&2
    exit 1
fi
sudo ln -s '{candidate}' /opt/attendance/current.next
sudo mv -Tf /opt/attendance/current.next /opt/attendance/current
sudo install -m 644 -o root -g root '{candidate}/deploy/attendance.service' /etc/systemd/system/attendance.service
sudo systemctl daemon-reload
sudo systemctl enable --now attendance.service
sudo systemctl restart attendance.service
sleep 2
sudo -u attendance env PYTHONDONTWRITEBYTECODE=1 /opt/attendance/venv/bin/python '{candidate}/deploy/check_service.py' --live
systemctl is-active attendance.service
systemctl is-enabled attendance.service
ss -lnt | grep '127.0.0.1:8000'
'''
    # Remove only the temporary, generated credential copy; preserve release/archive for review.
    if args.activate and args.domain:
        script += f"\nATTENDANCE_DOMAIN='{args.domain}'\nATTENDANCE_RELEASE='{candidate}'\n"
        script += (ROOT / 'deploy/https.sh').read_text(encoding='utf-8')
    script += 'rm -f "$stage/attendance.env"\n'
    run_script(script)
    result = {'host': args.host, 'release': release, 'candidate': candidate,
              'active': args.activate, 'domain': args.domain, 'local_port': 8765, 'remote_port': 8000}
    (ROOT / 'data/deployment.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
