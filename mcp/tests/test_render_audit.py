"""SVG 渲染与审计. """

import pytest

from scifig_mcp.tools.render import build_svg, render_to_svg
from scifig_mcp.tools.audit import audit_ir

SAMPLE = {
    "title": "图1 框架",
    "direction": "LR",
    "groups": [{"id": "g1", "label": "输入"}],
    "lanes": [{"id": "l1", "label": "阶段A"}],
    "nodes": [
        {"id": "n1", "label": "数据预处理", "group": "g1", "lane": "l1", "shape": "round"},
        {"id": "n2", "label": "模型", "group": "g1", "shape": "box"},
    ],
    "edges": [{"id": "e1", "source": "n1", "target": "n2", "label": "特征", "style": "solid"}],
    "locks": {"nodes": [], "edges": [], "groups": []},
}


def test_build_svg_ok():
    svg = build_svg(SAMPLE, "okabe-ito")
    assert svg.startswith("<svg")
    assert "n1" in svg or "模型" in svg or "数据预处理" in svg


def test_build_svg_invalid_raises():
    bad = {**SAMPLE, "edges": [{"source": "x", "target": "n2"}]}
    with pytest.raises(ValueError):
        build_svg(bad, "okabe-ito")


def test_render_to_svg_writes_file(tmp_path):
    p = tmp_path / "out.svg"
    render_to_svg(SAMPLE, str(p))
    assert p.exists()
    assert p.read_text(encoding="utf-8").startswith("<svg")


def test_manual_positions_are_used_for_reference_style_layout():
    ir = {
        "direction": "LR",
        "nodes": [
            {"id": "a", "label": "A", "position": {"x": 180, "y": 200}},
            {"id": "b", "label": "B", "position": {"x": 520, "y": 420}},
        ],
        "edges": [{"id": "e", "source": "a", "target": "b"}],
    }

    svg = build_svg(ir, "paper-soft")

    assert 'x="180.0"' in svg
    assert 'y="206.0"' in svg


def test_audit_passes_for_good():
    aud = audit_ir(SAMPLE)
    assert aud["passed"] is True
    assert aud["hard_failure_count"] == 0


def test_audit_catches_invalid():
    bad = {**SAMPLE, "edges": [{"source": "ghost", "target": "n2"}]}
    aud = audit_ir(bad)
    assert aud["passed"] is False


def test_audit_isolated_node_warning():
    ir = {
        **SAMPLE,
        "nodes": [{"id": "n1", "label": "a"}, {"id": "n2", "label": "b"}],
        "edges": [],
    }
    aud = audit_ir(ir)
    assert any(f["category"] == "isolated-node" for f in aud["findings"])


def test_audit_empty_label_warning():
    ir = {**SAMPLE, "nodes": [{"id": "n1", "label": ""}, {"id": "n2", "label": "b"}]}
    aud = audit_ir(ir)
    assert any(f["category"] == "empty-label" for f in aud["findings"])


def test_audit_empty_group_warning():
    ir = {
        **SAMPLE,
        "groups": [{"id": "g9", "label": "空组"}],
        "nodes": [{"id": "n1", "label": "a"}, {"id": "n2", "label": "b"}],
    }
    aud = audit_ir(ir)
    assert any(f["category"] == "empty-group" for f in aud["findings"])
