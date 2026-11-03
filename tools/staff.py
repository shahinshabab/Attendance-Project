"""Create an explicitly named employee or bind an enrolled sensor slot."""
import argparse
import json
import os
import urllib.error
import urllib.request

from backend.app import load_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='https://attendance.shahinanalytics.com')
    parser.add_argument('--code', required=True)
    parser.add_argument('--name')
    parser.add_argument('--device', default='office-01')
    parser.add_argument('--slot', type=int)
    args = parser.parse_args()
    if not args.server.startswith('https://'):
        parser.error('Use the public HTTPS server URL')
    load_env()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)

    def api(path, body=None):
        headers = {'X-API-Key': os.environ['ADMIN_API_KEY']}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(args.server.rstrip('/') + path, headers=headers,
                                         data=json.dumps(body).encode() if body is not None else None)
        with opener.open(request, timeout=15) as response:
            return json.load(response)

    employees = api('/api/employees')
    existing = next((e for e in employees if e['code'] == args.code), None)
    if args.name:
        if existing and (existing['name'] != args.name or not existing['active']):
            raise RuntimeError('Existing employee differs; refusing to overwrite it')
        if not existing:
            api('/api/employees', {'code': args.code, 'name': args.name, 'active': True})
        print('Staff ready:', args.code, args.name)
    elif not existing:
        parser.error('Employee does not exist; supply --name to create it')
    if args.slot is not None:
        result = api('/api/bindings', {'device_id': args.device, 'template_id': args.slot, 'employee_code': args.code})
        print('Sensor slot assigned:', json.dumps(result))


if __name__ == '__main__':
    main()
