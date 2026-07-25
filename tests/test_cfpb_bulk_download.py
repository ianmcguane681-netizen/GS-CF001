"""Coverage for the bulk-download access adapter.

The adapter previously held the whole official archive in memory as bytes before
opening it, which cannot work for a file that is hundreds of megabytes compressed.
It now streams to disk; these tests pin both the path-based and the injected
bytes-based routes, and the row limit that keeps expansion bounded.
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from connectors.cfpb import (
    CFPB_CREDIT_REPORTING_PRODUCT,
    CFPBBulkDownloadAccessAdapter,
)

OTHER_PRODUCT = "Mortgage"


def build_archive(rows: int = 5) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["Complaint ID", "Product", "Company", "Issue"])
    writer.writeheader()
    for index in range(rows):
        writer.writerow(
            {
                "Complaint ID": str(index),
                # Interleave a non-matching product to prove filtering works.
                "Product": CFPB_CREDIT_REPORTING_PRODUCT if index % 2 == 0 else OTHER_PRODUCT,
                "Company": f"Company {index}",
                "Issue": "Investigation into an existing problem",
            }
        )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w") as zipped:
        zipped.writestr("complaints.csv", buffer.getvalue())
    return archive.getvalue()


def test_extract_from_zip_accepts_bytes():
    adapter = CFPBBulkDownloadAccessAdapter(opener=lambda _url: build_archive())

    records = adapter._extract_from_zip(build_archive(), limit=10)

    assert [record["complaint_id"] for record in records] == ["0", "2", "4"]


def test_extract_from_zip_accepts_a_path(tmp_path: Path):
    archive_path = tmp_path / "complaints.csv.zip"
    archive_path.write_bytes(build_archive())
    adapter = CFPBBulkDownloadAccessAdapter()

    records = adapter._extract_from_zip(archive_path, limit=10)

    assert [record["complaint_id"] for record in records] == ["0", "2", "4"]


def test_extract_stops_at_the_limit():
    adapter = CFPBBulkDownloadAccessAdapter()

    records = adapter._extract_from_zip(build_archive(rows=100), limit=2)

    assert len(records) == 2


def test_injected_opener_is_used_and_records_a_diagnostic():
    adapter = CFPBBulkDownloadAccessAdapter(opener=lambda _url: build_archive())

    url, records, errors, diagnostics = adapter.retrieve(limit=2)

    assert errors == []
    assert len(records) == 2
    assert url.endswith("complaints.csv.zip")
    assert diagnostics[0].access_method == "official_cfpb_bulk_download"
    assert records[0]["_access_method"] == "official_cfpb_bulk_download"


def test_transport_failure_is_reported_as_a_diagnostic_not_an_exception():
    def failing_opener(_url: str) -> bytes:
        raise RuntimeError("curl transport failed (exit 28)")

    adapter = CFPBBulkDownloadAccessAdapter(opener=failing_opener)

    _url, records, errors, diagnostics = adapter.retrieve(limit=1)

    assert records == []
    assert errors and "curl transport failed" in errors[0]
    assert diagnostics[0].response_status == "error"
