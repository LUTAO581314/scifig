from pathlib import Path

from scifig_mcp.plugins import PluginRegistry
from scifig_mcp.workflow import FigureWorkflow


IR = {
    "title": "方法总览",
    "direction": "LR",
    "groups": [{"id": "g1", "label": "处理"}],
    "nodes": [
        {"id": "n1", "label": "输入", "group": "g1", "shape": "round"},
        {"id": "n2", "label": "输出", "group": "g1", "shape": "round"},
    ],
    "edges": [{"id": "e1", "source": "n1", "target": "n2", "style": "solid"}],
    "locks": {"nodes": [], "edges": [], "groups": []},
}


def _registry(tmp_path, *, passed=True, qa=None):
    calls = []

    def parse(path, tier, visual):
        return "# Demo\n\n方法：输入到输出。", {"stem": "demo", "visual": {"enabled": visual}}

    def planner(text, requirement):
        return {"paper_type": "method", "figure_irs": [IR], "parts": [], "notes": "ok"}

    def audit(ir):
        return {"passed": passed, "hard_failure_count": 0 if passed else 1,
                "warning_count": 0, "findings": [] if passed else [
                    {"category": "test", "severity": "hard", "message": "test failure"}
                ]}

    def render(ir, path, scheme):
        calls.append(Path(path).suffix)
        Path(path).write_text("artifact", encoding="utf-8")
        return path

    def vision(*args, **kwargs):
        if isinstance(qa, Exception):
            raise qa
        return qa or {"answer": "字号清晰", "usage": {}}

    registry = PluginRegistry(
        document_parser=parse, planner=planner, auditor=audit,
        render_svg=render, render_pptx=render, render_emf=render,
        vision_qa=vision,
        render_png=render, render_pdf=render,
    )
    return registry, calls


def test_prepare_returns_draft_and_persists_source(tmp_path):
    registry, calls = _registry(tmp_path)
    result = FigureWorkflow(registry).prepare("paper.pdf", artifact_dir=str(tmp_path))

    assert result["status"] == "draft"
    assert result["figures"][0]["renderable"] is True
    assert calls == []
    assert Path(result["source"]["parsed_document_path"]).exists()


def test_codex_mode_returns_evidence_without_calling_planner(tmp_path):
    registry, calls = _registry(tmp_path)
    result = FigureWorkflow(registry).prepare(
        "paper.pdf", planner_mode="codex", artifact_dir=str(tmp_path)
    )

    assert result["status"] == "evidence"
    assert result["mode"] == "codex"
    assert result["parsed_text"].startswith("# Demo")
    assert "figures" not in result
    assert calls == []


def test_render_requires_confirmation(tmp_path):
    registry, calls = _registry(tmp_path)
    result = FigureWorkflow(registry).render_confirmed(
        IR, confirmed=False, out_dir=str(tmp_path), formats=["svg"]
    )

    assert result["status"] == "awaiting_confirmation"
    assert calls == []


def test_audit_failure_blocks_delivery(tmp_path):
    registry, calls = _registry(tmp_path, passed=False)
    result = FigureWorkflow(registry).render_confirmed(
        IR, confirmed=True, out_dir=str(tmp_path), formats=["svg"]
    )

    assert result["status"] == "blocked"
    assert calls == []


def test_confirmed_render_returns_editable_outputs_and_qa_suggestions(tmp_path):
    registry, calls = _registry(tmp_path, qa=RuntimeError("vision unavailable"))
    result = FigureWorkflow(registry).render_confirmed(
        IR, confirmed=True, out_dir=str(tmp_path), formats=["svg", "pptx", "png"],
        qa_mode="mcp",
    )

    assert result["status"] == "complete"
    assert set(result["outputs"]) == {"svg", "pptx", "png"}
    assert all(Path(path).exists() for path in result["outputs"].values())
    assert result["qa"]["status"] == "unavailable"
    assert result["suggestions"]
    assert calls == [".svg", ".pptx", ".png"]


def test_codex_qa_is_delegated_without_vision_api(tmp_path):
    registry, calls = _registry(tmp_path)
    result = FigureWorkflow(registry).render_confirmed(
        IR, confirmed=True, out_dir=str(tmp_path), formats=["svg"],
    )

    assert result["status"] == "complete"
    assert result["qa"]["status"] == "delegated"
    assert result["qa"]["mode"] == "codex"
