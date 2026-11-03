import io
import json
from unittest.mock import patch

import pytest

from tools.device import deliver


def test_remote_plaintext_refused():
    with pytest.raises(ValueError, match='HTTPS'):
        deliver('http://office.example.com', 'secret', {'event_id': 'event-0001'})


@pytest.mark.parametrize('status,identity,expected', [('recorded','event-0001',True),('duplicate','event-0001',True),('unmapped','event-0001',True),('recorded','wrong-id',False),('error','event-0001',False)])
def test_ack_requires_exact_server_acceptance(status, identity, expected):
    response = io.BytesIO(json.dumps({'event_id': identity, 'status': status}).encode())
    with patch('urllib.request.build_opener') as builder:
        builder.return_value.open.return_value = response
        assert deliver('http://127.0.0.1:8000', 'secret', {'event_id': 'event-0001'}) is expected
