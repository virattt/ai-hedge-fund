"""Tests for autoresearch.sector_correlation."""

def test_sector_config():
    from autoresearch.portfolio_backtest import SECTOR_CONFIG
    assert "memory" in SECTOR_CONFIG
    assert "tech" in SECTOR_CONFIG
    assert "equipment" in SECTOR_CONFIG
