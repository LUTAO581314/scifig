from pathlib import Path

import pymupdf as fitz

from scifig_mcp.tools.parse import collect_visual_evidence


def test_codex_visual_evidence_renders_candidate_pdf_pages(tmp_path):
    paper = tmp_path / "paper.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Figure 1. System architecture")
    doc.save(str(paper))
    doc.close()

    result = collect_visual_evidence(str(paper), str(tmp_path / "evidence"))

    assert result["mode"] == "codex"
    assert result["status"] == "ready"
    assert result["pages"] == [1]
    assert Path(result["artifacts"][0]["path"]).exists()
