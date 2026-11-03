"""Run a checked-in UTF-8 shell script over the configured attendance SSH alias."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='Attendance-Server')
    parser.add_argument('--config', default=str(Path.home() / '.ssh/config'))
    parser.add_argument('script', type=Path)
    args = parser.parse_args()
    executable = str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/OpenSSH/ssh.exe') if os.name == 'nt' else 'ssh'
    script = args.script.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
    command = [executable, '-F', args.config, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'ConnectTimeout=15', args.host, 'sh -s']
    result = subprocess.run(command, input=script.encode('utf-8'))
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
