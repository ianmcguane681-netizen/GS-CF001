"""Focused tests for the curl-based CFPB transport.

These tests exercise `_curl_fetch`, `_parse_curl_headers`, and `CFPBTransportHTTPError`
in isolation by stubbing `subprocess.run` and `shutil.which` — no real network or curl
binary is required. They also lock in the query-parameter fix that keeps the official
search API in filtered/size-limited mode instead of full-export mode.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from connectors.cfpb import (
    CFPBAPIAccessAdapter,
    CFPBTransportHTTPError,
    _curl_fetch,
    _parse_curl_headers,
    _require_curl,
)


def _command_paths(command: list[str]) -> tuple[Path, Path]:
    """Extract the -o (body) and -D (headers) output paths from a curl command list."""
    body_path = Path(command[command.index("-o") + 1])
    header_path = Path(command[command.index("-D") + 1])
    return body_path, header_path


class FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_curl_fetch_success(monkeypatch):
    def fake_which(_name):
        return "/usr/bin/curl"

    def fake_run(command, capture_output, text, timeout):
        body_path, header_path = _command_paths(command)
        body_path.write_bytes(b'{"ok": true}')
        header_path.write_text("HTTP/2 200\r\ncontent-type: application/json\r\n\r\n")
        return FakeCompletedProcess(returncode=0, stdout="200")

    monkeypatch.setattr("connectors.cfpb.shutil.which", fake_which)
    monkeypatch.setattr("connectors.cfpb.subprocess.run", fake_run)

    body, headers, status = _curl_fetch("https://example.test/api", {"Accept": "application/json"})

    assert body == b'{"ok": true}'
    assert headers["content-type"] == "application/json"
    assert status == 200


def test_curl_fetch_non_2xx_raises_transport_http_error(monkeypatch):
    def fake_which(_name):
        return "/usr/bin/curl"

    def fake_run(command, capture_output, text, timeout):
        body_path, header_path = _command_paths(command)
        body_path.write_bytes(b"Access Denied")
        header_path.write_text("HTTP/2 403\r\nserver: AkamaiGHost\r\n\r\n")
        return FakeCompletedProcess(returncode=0, stdout="403")

    monkeypatch.setattr("connectors.cfpb.shutil.which", fake_which)
    monkeypatch.setattr("connectors.cfpb.subprocess.run", fake_run)

    with pytest.raises(CFPBTransportHTTPError) as excinfo:
        _curl_fetch("https://example.test/api", {"Accept": "application/json"})

    exc = excinfo.value
    assert exc.code == 403
    assert exc.headers["server"] == "AkamaiGHost"
    assert exc.read() == b"Access Denied"


def test_curl_fetch_timeout_or_transport_failure_raises_runtime_error(monkeypatch):
    def fake_which(_name):
        return "/usr/bin/curl"

    def fake_run(command, capture_output, text, timeout):
        # curl exit code 28 == "Operation timed out"
        return FakeCompletedProcess(returncode=28, stdout="", stderr="curl: (28) Operation timed out after 45000 milliseconds")

    monkeypatch.setattr("connectors.cfpb.shutil.which", fake_which)
    monkeypatch.setattr("connectors.cfpb.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="curl transport failed"):
        _curl_fetch("https://example.test/api", {})


def test_curl_fetch_propagates_subprocess_timeout_expired(monkeypatch):
    def fake_which(_name):
        return "/usr/bin/curl"

    def fake_run(command, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

    monkeypatch.setattr("connectors.cfpb.shutil.which", fake_which)
    monkeypatch.setattr("connectors.cfpb.subprocess.run", fake_run)

    with pytest.raises(subprocess.TimeoutExpired):
        _curl_fetch("https://example.test/api", {})


def test_curl_fetch_missing_curl_raises_runtime_error(monkeypatch):
    def fake_which(_name):
        return None

    monkeypatch.setattr("connectors.cfpb.shutil.which", fake_which)

    with pytest.raises(RuntimeError, match="curl is required"):
        _require_curl()

    with pytest.raises(RuntimeError, match="curl is required"):
        _curl_fetch("https://example.test/api", {})


def test_curl_fetch_malformed_json_raises_on_decode(monkeypatch):
    def fake_which(_name):
        return "/usr/bin/curl"

    def fake_run(command, capture_output, text, timeout):
        body_path, header_path = _command_paths(command)
        body_path.write_bytes(b"not-valid-json{{{")
        header_path.write_text("HTTP/2 200\r\ncontent-type: application/json\r\n\r\n")
        return FakeCompletedProcess(returncode=0, stdout="200")

    monkeypatch.setattr("connectors.cfpb.shutil.which", fake_which)
    monkeypatch.setattr("connectors.cfpb.subprocess.run", fake_run)

    adapter = CFPBAPIAccessAdapter()
    with pytest.raises(json.JSONDecodeError):
        adapter._default_fetch_json("https://example.test/api")


def test_curl_fetch_uses_only_final_header_block_after_redirect(monkeypatch):
    def fake_which(_name):
        return "/usr/bin/curl"

    def fake_run(command, capture_output, text, timeout):
        body_path, header_path = _command_paths(command)
        body_path.write_bytes(b'{"final": true}')
        # curl's -D captures a header block per hop when following redirects.
        header_path.write_text(
            "HTTP/1.1 301 Moved Permanently\r\n"
            "location: https://example.test/api/final\r\n"
            "\r\n"
            "HTTP/2 200\r\n"
            "content-type: application/json\r\n"
            "x-final-hop: true\r\n"
            "\r\n"
        )
        return FakeCompletedProcess(returncode=0, stdout="200")

    monkeypatch.setattr("connectors.cfpb.shutil.which", fake_which)
    monkeypatch.setattr("connectors.cfpb.subprocess.run", fake_run)

    body, headers, status = _curl_fetch("https://example.test/api", {})

    assert status == 200
    assert body == b'{"final": true}'
    assert headers == {"content-type": "application/json", "x-final-hop": "true"}
    assert "location" not in headers


def test_parse_curl_headers_missing_file_returns_empty_dict(tmp_path):
    missing_path = tmp_path / "does-not-exist"
    assert _parse_curl_headers(missing_path) == {}


def test_build_url_does_not_send_unsafe_full_export_parameters():
    """Regression guard: `format=json&no_aggs=true` switched the live API into a
    full-database export/attachment mode that ignores `size`/`product` filtering.
    These params must never reappear in the built URL."""
    adapter = CFPBAPIAccessAdapter()

    url = adapter.build_url(limit=3)

    assert "format=json" not in url
    assert "no_aggs" not in url
    assert "size=3" in url
    assert "Credit+reporting" in url
