from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber
from test_api import PASSWORD, account

from app.api import auth
from app.core.config import settings
from app.services import storage


def test_smtp_password_reset_contract_with_mock_transport(client, monkeypatch):
    config = settings()
    monkeypatch.setattr(config, "smtp_host", "mail.example")
    monkeypatch.setattr(config, "smtp_from", "workspace@example.com")
    monkeypatch.setattr(config, "smtp_username", "fixture-sender")
    monkeypatch.setattr(config, "smtp_password", "fixture-secret")
    email, _, _ = account(client)
    events = []

    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("mail.example", 587, 8)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def starttls(self, context):
            assert context.check_hostname
            events.append("tls")

        def login(self, username, password):
            assert (username, password) == ("fixture-sender", "fixture-secret")
            events.append("login")

        def send_message(self, message):
            assert message["To"] == email
            assert message["From"] == "workspace@example.com"
            events.append(message.get_content().splitlines()[-1])

    monkeypatch.setattr(auth.smtplib, "SMTP", SMTP)
    assert client.post("/api/auth/forgot", json={"email": email}).status_code == 202
    assert events[:2] == ["tls", "login"]
    link = urlsplit(events[2])
    assert link.path == "/reset"
    token = parse_qs(link.query)["token"][0]
    new_password = "new fixture password 456"
    request = {"token": token, "password": new_password}
    assert client.post("/api/auth/reset", json=request).status_code == 200
    assert client.post("/api/auth/reset", json=request).status_code == 400
    assert client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": new_password}).status_code == 200


def test_s3_object_storage_contract_with_stubbed_client(monkeypatch):
    configured = settings()
    monkeypatch.setattr(configured, "s3_bucket", "analyst-fixture")
    s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test")
    monkeypatch.setattr(storage, "client", lambda: s3)
    key = "reports/fixture/example.csv"
    content = b"region,revenue\nNorth,105\n"
    params = {"Bucket": "analyst-fixture", "Key": key}
    stream = BytesIO(content)
    with Stubber(s3) as stub:
        stub.add_response("put_object", {}, params | {"Body": content})
        stub.add_response("get_object", {"Body": StreamingBody(stream, len(content))}, params)
        stub.add_response("delete_object", {}, params)
        storage.put(key, content)
        assert storage.read(key) == content
        assert stream.closed
        storage.remove(key)
        stub.assert_no_pending_responses()
