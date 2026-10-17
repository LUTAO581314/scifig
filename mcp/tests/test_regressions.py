"""回归测试：真实论文出图时暴露过的 bug，不得复发。

1. 多泳道 pipeline 的 LR 布局方向（曾反了：起点在最右）
2. render_to_* 输出扩展名自动补全（曾生成无扩展名文件）
3. render_to_emf 在 PIL 不会真正写 EMF 时的回退（曾只捕获 ImportError）
4. decompose._focus_text 长文截断保留方法章节（曾是简单头部截断）
"""

import os

from scifig_mcp.tools.render import (
    _layout,
    render_to_emf,
    render_to_pptx,
    render_to_svg,
)
from scifig_mcp.tools.decompose import _focus_text

# 真实论文（tsfresh-FSA-TW）同款结构：3 泳道 + n1..n7 链式 pipeline
PIPELINE = {
    "title": "图1 框架",
    "direction": "LR",
    "groups": [
        {"id": "g1", "label": "A"},
        {"id": "g2", "label": "B"},
        {"id": "g3", "label": "C"},
    ],
    "lanes": [
        {"id": "l1", "label": "阶段A"},
        {"id": "l2", "label": "阶段B"},
        {"id": "l3", "label": "阶段C"},
    ],
    "nodes": [
        {"id": "n1", "label": "a", "group": "g1", "lane": "l1", "shape": "cylinder"},
        {"id": "n2", "label": "b", "group": "g1", "lane": "l1", "shape": "box"},
        {"id": "n3", "label": "c", "group": "g1", "lane": "l1", "shape": "diamond"},
        {"id": "n4", "label": "d", "group": "g2", "lane": "l2", "shape": "box"},
        {"id": "n5", "label": "e", "group": "g2", "lane": "l2", "shape": "parallelogram"},
        {"id": "n6", "label": "f", "group": "g3", "lane": "l3", "shape": "box"},
        {"id": "n7", "label": "g", "group": "g3", "lane": "l3", "shape": "ellipse"},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
        {"id": "e3", "source": "n3", "target": "n4"},
        {"id": "e4", "source": "n4", "target": "n5"},
        {"id": "e5", "source": "n5", "target": "n6"},
        {"id": "e6", "source": "n6", "target": "n7"},
    ],
    "locks": {"nodes": [], "edges": [], "groups": []},
}


def test_pipeline_lr_direction_start_left_end_right():
    nc, layers, _, _ = _layout(PIPELINE)
    # 拓扑层：起点=0，终点=最大，沿链单调递增
    assert layers["n1"] == 0
    assert layers["n7"] == 6
    chain = ["n1", "n2", "n3", "n4", "n5", "n6", "n7"]
    xs = [nc[i][0] for i in chain]
    assert xs == sorted(xs), f"LR 布局 x 坐标必须沿数据流单调不减: {xs}"
    # LR：起点最左，终点最右
    assert nc["n1"][0] < nc["n7"][0]


def test_render_ext_autofill(tmp_path):
    p = render_to_pptx(PIPELINE, str(tmp_path / "noext"))
    assert p.endswith(".pptx") and os.path.exists(p)

    s = render_to_svg(PIPELINE, str(tmp_path / "noext2"))
    assert s.endswith(".svg") and os.path.exists(s)
    assert open(s, encoding="utf-8").read().startswith("<svg")

    e = render_to_emf(PIPELINE, str(tmp_path / "noext3"))
    assert e.endswith(".emf") and os.path.exists(e)


def test_render_emf_never_raises_and_delivers_preview(tmp_path):
    out = render_to_emf(PIPELINE, str(tmp_path / "fig.emf"))
    assert os.path.exists(out)
    base = out[: -len(".emf")]
    # PIL 不会真正写 EMF 时必须有 SVG 预览兜底
    assert os.path.exists(base + "_preview.svg") or os.path.getsize(out) > 120


def test_focus_text_keeps_method_section():
    intro = "# 论文标题\n" + "摘要摘要摘要。" * 1500
    filler = "\n## 1 引言\n" + "引言内容引言内容。" * 4000
    method = "\n## 2 方法\n" + "方法核心内容。" * 4000
    refs = "\n## 5 参考文献\n" + "ref entry " * 3000
    text = intro + filler + method + refs
    assert len(text) > 8000

    out = _focus_text(text, limit=8000)
    assert len(out) <= 8000
    # 方法章节必须被保留（头部截断时它会被丢掉）
    assert "方法核心内容" in out
    # 摘要保留
    assert "摘要摘要摘要" in out


def test_focus_text_short_text_unchanged():
    text = "# t\n" + "body " * 100
    assert _focus_text(text, limit=8000) == text.strip()


def test_focus_text_no_headings_fallback():
    text = "x" * 20000
    out = _focus_text(text, limit=8000)
    assert len(out) <= 8000
    assert "[中间截断]" in out


def test_text_w_cjk_vs_latin():
    from scifig_mcp.tools.render import _text_w
    # 4 个 CJK 字符在 14px 下应估约 56px（旧公式 len*9+12=48 导致边标签背景框偏窄）
    assert _text_w("特征矩阵", 14) > 50
    assert _text_w("abcd", 14) < _text_w("特征", 14) + 28
    # 混合：滚动90%分位标签 = 6 CJK*16 + 3 半角*9.6 ≈ 124.8
    assert 120 < _text_w("滚动90%分位标签", 16) < 135


def test_paper_soft_scheme():
    from scifig_mcp.palette import get_scheme
    sc = get_scheme("paper-soft")
    assert sc["primary"]["fill"] != sc["primary"]["stroke"]  # 浅填充+深描边分离


def test_svg_uses_ortho_path_for_lr():
    from scifig_mcp.tools.render import build_svg
    svg = build_svg(PIPELINE, "paper-soft")
    # LR 用折线 path + 圆角
    assert "<path d=" in svg
    assert " marker-end=\"url(#arrow)\"" in svg
    assert "Q " in svg  # 圆角二次贝塞尔


def test_svg_node_desc_renders_two_lines():
    ir = {
        **PIPELINE,
        "nodes": [{"id": "n1", "label": "数据", "desc": "说明文字", "shape": "round"},
                  {"id": "n2", "label": "模型", "shape": "box"}],
        "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
    }
    from scifig_mcp.tools.render import build_svg
    svg = build_svg(ir, "paper-soft")
    assert "说明文字" in svg
    # 有 desc 的节点用两次小号文字（标题+说明）
    assert 'font-size="11.5"' in svg
