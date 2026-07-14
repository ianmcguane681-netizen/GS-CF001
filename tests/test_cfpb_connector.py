from connectors.cfpb import CFPBConnector, CFPB_CREDIT_REPORTING_PRODUCT


def sample_payload():
    return {
        "hits": {
            "hits": [
                {
                    "_id": "123",
                    "_source": {
                        "complaint_id": "123",
                        "product": CFPB_CREDIT_REPORTING_PRODUCT,
                        "issue": "Incorrect information on your report",
                        "company": "Example Bank",
                        "complaint_what_happened": "The company did not correct information after my dispute.",
                    },
                }
            ]
        }
    }


def test_cfpb_connector_builds_credit_reporting_url():
    connector = CFPBConnector(fetch_json=lambda _url: sample_payload())

    url = connector.build_url(limit=1)

    assert "consumerfinance.gov" in url
    assert "Credit+reporting" in url
    assert "size=1" in url


def test_cfpb_connector_preserves_raw_records_and_retrieval_metadata():
    connector = CFPBConnector(fetch_json=lambda _url: sample_payload())

    result = connector.retrieve(limit=1)

    assert not result.errors
    assert result.source.role == "discovery"
    assert result.records[0]["complaint_id"] == "123"
    assert result.records[0]["_retrieval_url"] == result.retrieval_url
    assert result.records[0]["_retrieved_at"] == result.retrieved_at
    assert result.records[0]["_access_method"] == "official_cfpb_search_api"
    assert result.diagnostics[0].response_status == "200"
    assert result.source_reliability.source_family == "CFPB complaints"
