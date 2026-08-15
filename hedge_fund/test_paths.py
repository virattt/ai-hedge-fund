from pathlib import Path

import pytest

from hedge_fund import paths


def test_ensure_mandates_dir_seeds_example_into_existing_directory(tmp_path, monkeypatch):
    mandate_dir = tmp_path / "mandates"
    mandate_dir.mkdir()
    source_example = tmp_path / "example.yaml"
    source_example.write_text("name: example\n", encoding="utf-8")

    monkeypatch.setattr(paths, "MANDATES_DIR", mandate_dir)
    monkeypatch.setattr(paths, "EXAMPLE_MANDATE", source_example)

    result = paths.ensure_mandates_dir()

    assert result == mandate_dir
    assert (mandate_dir / "example.yaml").read_text(encoding="utf-8") == "name: example\n"


def test_ensure_mandates_dir_does_not_overwrite_existing_example(tmp_path, monkeypatch):
    mandate_dir = tmp_path / "mandates"
    mandate_dir.mkdir()
    existing_example = mandate_dir / "example.yaml"
    existing_example.write_text("name: customized\n", encoding="utf-8")
    source_example = tmp_path / "example.yaml"
    source_example.write_text("name: shipped\n", encoding="utf-8")

    monkeypatch.setattr(paths, "MANDATES_DIR", mandate_dir)
    monkeypatch.setattr(paths, "EXAMPLE_MANDATE", source_example)

    paths.ensure_mandates_dir()

    assert existing_example.read_text(encoding="utf-8") == "name: customized\n"


def test_ensure_mandates_dir_rejects_existing_file(tmp_path, monkeypatch):
    mandate_path = tmp_path / "mandates"
    mandate_path.write_text("not a directory", encoding="utf-8")

    monkeypatch.setattr(paths, "MANDATES_DIR", mandate_path)

    with pytest.raises(NotADirectoryError, match="not a directory"):
        paths.ensure_mandates_dir()
