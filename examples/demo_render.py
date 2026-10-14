"""渲染链路示例：Diagram IR → SVG/PPTX/EMF + 审计。

用法：python examples/demo_render.py
会生成 loot/demo.svg、demo.pptx、demo.emf(_preview.svg)。
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp" / "src"))

from scifig_mcp.diagram_ir import validate_ir, format_ir_for_regeneration
from scifig_mcp.tools.audit import audit_ir
from scifig_mcp.tools.render import render_to_svg, render_to_pptx, render_to_emf

# Diagram IR（拆解确认闸门的核心数据结构）
IR = {
    "title": "图1 系统整体框架",
    "direction": "LR",
    "groups": [
        {"id": "g1", "label": "输入层"},
        {"id": "g2", "label": "处理层"},
        {"id": "g3", "label": "输出层"},
    ],
    "lanes": [
        {"id": "l1", "label": "数据准备"},
        {"id": "l2", "label": "模型推理"},
    ],
    "nodes": [
        {"id": "n1", "label": "数据预处理", "group": "g1", "lane": "l1", "shape": "parallelogram"},
        {"id": "n2", "label": "特征提取", "group": "g1", "lane": "l1", "shape": "round"},
        {"id": "n3", "label": "主模型", "group": "g2", "lane": "l2", "shape": "box"},
        {"id": "n4", "label": "后处理", "group": "g2", "lane": "l2", "shape": "diamond"},
        {"id": "n5", "label": "结果输出", "group": "g3", "lane": "l2", "shape": "cylinder"},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n3", "label": "特征", "style": "solid"},
        {"id": "e2", "source": "n2", "target": "n3", "label": "特征", "style": "solid"},
        {"id": "e3", "source": "n3", "target": "n4", "label": "中间结果", "style": "solid"},
        {"id": "e4", "source": "n4", "target": "n5", "label": "结果", "style": "dashed"},
    ],
    "locks": {"nodes": ["n3"], "edges": [], "groups": []},
    "caption": "图1 系统整体框架示意图",
}


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "loot"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 校验 IR
    errors = validate_ir(IR)
    print("validate:", "OK" if not errors else errors)

    # 2. 锁定重生成展示
    print("\n--- 拆解确认展示（带 LOCKED）---")
    print(format_ir_for_regeneration(IR))

    # 3. 审计
    audit = audit_ir(IR)
    print("\n--- 审计 ---")
    print(f"passed={audit['passed']} hard={audit['hard_failure_count']} warn={audit['warning_count']}")

    # 4. 渲染三格式
    print("\n--- 渲染 ---")
    print("SVG :", render_to_svg(IR, str(out_dir / "demo.svg")))
    try:
        print("PPTX:", render_to_pptx(IR, str(out_dir / "demo.pptx")))
    except RuntimeError as e:
        print("PPTX 跳过:", e)
    print("EMF :", render_to_emf(IR, str(out_dir / "demo.emf")))


if __name__ == "__main__":
    main()
