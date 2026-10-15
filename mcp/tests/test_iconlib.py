"""图标库：搜索与解析（用临时模拟目录，不联网）。"""

import os

import pytest

from scifig_mcp import iconlib


@pytest.fixture
def fake_bioicons(tmp_path, monkeypatch):
    """构造一个最小的本地 Bioicons 目录结构。"""
    icons = tmp_path / "static" / "icons"
    # cc-0/Nucleic_acids/Kumar/DNA.svg
    d1 = icons / "cc-0" / "Nucleic_acids" / "Kumar"
    d1.mkdir(parents=True)
    (d1 / "DNA.svg").write_text('<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>', encoding="utf-8")
    (d1 / "RNA.svg").write_text('<svg viewBox="0 0 100 100"><rect width="100" height="100"/></svg>', encoding="utf-8")
    # cc-by-4.0/Cell_membrane/DBCLS/cell_membrane.svg
    d2 = icons / "cc-by-4.0" / "Cell_membrane" / "DBCLS"
    d2.mkdir(parents=True)
    (d2 / "cell_membrane.svg").write_text('<svg viewBox="0 0 100 100"><circle/></svg>', encoding="utf-8")

    monkeypatch.setenv("SCIFIG_BIOICONS_DIR", str(tmp_path))
    # 重置模块级缓存
    iconlib._local_index = None
    iconlib._remote_index = None
    return tmp_path


def test_local_categories(fake_bioicons):
    cats = iconlib.categories()
    assert "Nucleic_acids" in cats
    assert "Cell_membrane" in cats


def test_search_dna(fake_bioicons):
    hits = iconlib.search_icons("DNA")
    assert hits, "应找到 DNA 图标"
    assert any(h["name"] == "DNA" for h in hits)


def test_search_category_filter(fake_bioicons):
    hits = iconlib.search_icons("cell", category="Cell_membrane")
    assert hits and all(h["category"] == "Cell_membrane" for h in hits)


def test_resolve_string(fake_bioicons):
    e = iconlib.resolve_icon("DNA")
    assert e is not None and e["name"] == "DNA"


def test_resolve_dict(fake_bioicons):
    e = iconlib.resolve_icon({"name": "RNA", "category": "Nucleic_acids"})
    assert e is not None and e["name"] == "RNA"


def test_resolve_explicit_path(fake_bioicons):
    e = iconlib.resolve_icon({"path": "cc-0/Nucleic_acids/Kumar/DNA.svg"})
    assert e is not None and e["name"] == "DNA"


def test_fetch_local(fake_bioicons):
    e = iconlib.resolve_icon("DNA")
    txt = iconlib.fetch_icon_svg(e, as_text=True)
    assert "circle" in txt


def test_fetch_none(fake_bioicons):
    assert iconlib.resolve_icon(None) is None
    assert iconlib.resolve_icon("zzz_no_such_icon_999") is None
