from v2.data.client import FDClient


def test_get_earnings_preserves_filing_metadata(monkeypatch):
    payload = [
        {
            "ticker": "AAPL",
            "report_period": "2025-09-27",
            "source_type": "10-K",
            "filing_date": "2025-10-31",
            "filing_datetime": "2025-10-31T06:01:26Z",
            "filing_window": "after_market_close",
            "fiscal_period": "FY",
            "currency": "USD",
            "filing_url": "https://www.sec.gov/Archives/example.htm",
            "accession_number": "0000320193-25-000079",
            "quarterly": {"revenue": 102466000000, "earnings_per_share": 1.85},
        }
    ]

    client = FDClient(api_key="test")
    monkeypatch.setattr(client, "_get", lambda *args, **kwargs: payload)

    earnings = client.get_earnings("AAPL")

    assert earnings is not None
    assert earnings.source_type == "10-K"
    assert earnings.filing_date == "2025-10-31"
    assert earnings.filing_datetime == "2025-10-31T06:01:26Z"
    assert earnings.filing_window == "after_market_close"
    assert earnings.filing_url == "https://www.sec.gov/Archives/example.htm"
    assert earnings.accession_number == "0000320193-25-000079"
    assert earnings.quarterly is not None
    assert earnings.quarterly.revenue == 102466000000
