"""渲染链路示例：figure_spec → SVG/EMF。

用法：python examples/demo_render.py
会生成 loot/demo.svg 与 loot/demo.emf(*_preview.svg)。
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp" / "src"))

from scifig_mcp.tools.render import render_to_svg, render_to_emf

SPEC = {
    "title": "图1 系统整体框架",
    "direction": "LR",
    "groups": [
        {"name": "输入层", "color": "blues"},
        {"name": "处理层", "color": "greens"},
        {"name": "输出层", "color": "oranges"},
    ],
    "nodes": [
        {"id": "n1", "label": "数据预处理", "group": "输入层"},
        {"id": "n2", "label": "特征提取", "group": "输入层"},
        {"id": "n3", "label": "主模型", "group": "处理层"},
        {"id": "n4", "label": "后处理", "group": "处理层"},
        {"id": "n5", "label": "结果输出", "group": "输出层"},
    ],
    "edges": [
        {"from": "n1", "to": "n3", "label": "特征"},
        {"from": "n2", "to": "n3", "label": "特征"},
        {"from": "n3", "to": "n4", "label": "中间结果"},
        {"from": "n4", "to": "n5", "label": "结果"},
    ],
    "caption": "图1 系统整体框架示意图",
}


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "loot"
    out_dir.mkdir(parents=True, exist_ok=True)

    svg = render_to_svg(SPEC, str(out_dir / "demo.svg"))
    emf = render_to_emf(SPEC, str(out_dir / "demo.emf"))
    print("SVG:", svg)
    print("EMF:", emf)
    svg_preview = out_dir / "demo_preview.svg"
    if svg_preview.exists():
        print("Preview:", svg_preview)


if __name__ == "__main__":
    main()
