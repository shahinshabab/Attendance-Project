"""Write firmware/include/config.h for Wi-Fi mode without printing the device key."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import string

import certifi

from backend.app import load_env

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'firmware/include/config.h'
# Let's Encrypt (current issuer) plus ZeroSSL's roots, which Caddy uses if Let's Encrypt is unavailable.
ROOT_LABELS = ('ISRG Root X1', 'ISRG Root X2', 'USERTrust RSA Certification Authority', 'USERTrust ECC Certification Authority')


def root_certificates():
    bundle = Path(certifi.where()).read_text(encoding='ascii')
    found = []
    for label in ROOT_LABELS:
        match = re.search(r'# Label: "' + re.escape(label) + r'"\n.*?(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)', bundle, re.S)
        if not match:
            raise RuntimeError('Root certificate missing from certifi: ' + label)
        found.append(match.group(1))
    return '\n'.join(found)


def c_string(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def existing(text, name):
    match = re.search(r'constexpr char ' + name + r'\[\] = "((?:[^"\\]|\\.)*)";', text)
    return re.sub(r'\\(.)', r'\1', match.group(1)) if match else ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='https://attendance.shahinanalytics.com')
    parser.add_argument('--device', default='office-01')
    parser.add_argument('--fallback-ssid', help='Defaults to the current value, else Attendance-Setup')
    parser.add_argument('--fallback-password', help='Defaults to the current value, else a generated one')
    parser.add_argument('--show-fallback', action='store_true', help='Print the fallback hotspot name and password')
    args = parser.parse_args()
    if not re.fullmatch(r'https://[a-z0-9.-]+(:\d+)?', args.server):
        parser.error('Use an https:// origin with no path or trailing slash')
    load_env()
    key = json.loads(os.getenv('DEVICE_KEYS_JSON', '{}')).get(args.device, '')
    if len(key) < 24:
        raise RuntimeError(f'No device key for {args.device} in .env')
    text = CONFIG.read_text(encoding='utf-8') if CONFIG.exists() else CONFIG.with_name('config.example.h').read_text(encoding='utf-8')
    ssid = args.fallback_ssid or existing(text, 'FALLBACK_WIFI_SSID') or 'Attendance-Setup'
    alphabet = string.ascii_lowercase.replace('l', '') + '23456789'
    password = args.fallback_password or existing(text, 'FALLBACK_WIFI_PASSWORD') or ''.join(secrets.choice(alphabet) for _ in range(12))
    if not 1 <= len(ssid.encode()) <= 32 or not 8 <= len(password.encode()) <= 63:
        parser.error('Fallback SSID must be 1-32 bytes and password 8-63 characters')
    template = CONFIG.with_name('config.example.h').read_text(encoding='utf-8')
    values = {'DEVICE_ID': args.device, 'FALLBACK_WIFI_SSID': ssid, 'FALLBACK_WIFI_PASSWORD': password,
              'SERVER_URL': args.server, 'DEVICE_API_KEY': key}
    for name, value in values.items():
        template = re.sub(r'constexpr char ' + name + r'\[\] = "[^"]*";', lambda _: f'constexpr char {name}[] = {c_string(value)};', template)
    template = template.replace('constexpr bool USE_WIFI = false;', 'constexpr bool USE_WIFI = true;')
    template = re.sub(r'R"PEM\(.*?\)PEM"', lambda _: 'R"PEM(\n' + root_certificates() + '\n)PEM"', template, flags=re.S)
    CONFIG.write_text(template, encoding='utf-8')
    print(f'Wrote {CONFIG.relative_to(ROOT)} for {args.device} -> {args.server} (Wi-Fi mode, {len(ROOT_LABELS)} root CAs).')
    print(f'Fallback hotspot name: {ssid}')
    print('Fallback hotspot password: ' + (password if args.show_fallback else '(hidden; rerun with --show-fallback)'))


if __name__ == '__main__':
    main()
