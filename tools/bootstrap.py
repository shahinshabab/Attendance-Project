"""Create local secrets and firmware config without printing credentials."""
import json
from pathlib import Path
import secrets
import shutil

ROOT = Path(__file__).resolve().parent.parent


def main():
    env = ROOT / '.env'
    if not env.exists():
        env.write_text('ADMIN_API_KEY=' + secrets.token_urlsafe(32) + '\nDEVICE_KEYS_JSON=' +
                       json.dumps({'office-01': secrets.token_urlsafe(32)}) +
                       '\nDATABASE_PATH=data/attendance.sqlite3\nATTENDANCE_TIMEZONE=Asia/Kolkata\n', encoding='utf-8')
    config = ROOT / 'firmware/include/config.h'
    if not config.exists():
        shutil.copyfile(config.with_name('config.example.h'), config)
    print('Local configuration ready; secrets were not printed.')


if __name__ == '__main__':
    main()
