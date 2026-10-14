"""SciFig MCP server：论文解析 → 拆解(IR) → 可编辑科研图(SVG/PPTX/EMF)。

工具清单：
- parse_paper    : PDF → 结构化 markdown（可选，复用 MinerU）
- decompose      : 论文文本 + 需求 → Diagram IR JSON（LLM 拆解，含 locks）
- validate_ir    : 校验 Diagram IR 是否合法可渲染
- audit_ir       : 确定性质量审计（越界/密度/孤立节点等），passed gate
- render_svg     : Diagram IR → SVG 文件
- render_pptx    : Diagram IR → PPTX 文件（python-pptx 原生可编辑形状/连接线）
- render_emf     : Diagram IR → EMF 文件（预览）
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastmcp import FastMCP

from scifig_mcp.diagram_ir import validate_ir, ir_to_json
from scifig_mcp.llm.provider import get_llm
from scifig_mcp.tools.audit import audit_ir
from scifig_mcp.tools.decompose import decompose_paper
from scifig_mcp.tools.parse import parse_paper_file
from scifig_mcp.tools.render import render_to_svg, render_to_pptx, render_to_emf

mcp = FastMCP("scifig-mcp")

OUT_DIR = Path(os.environ.get("SCIFIG_OUT_DIR", "./loot")).resolve()


def _out(name: str, ext: str) -> Path:
    out = OUT_DIR / f"{name}.{ext}"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


@mcp.tool()
def parse_paper(pdf_path: str, tier: str = "basic") -> str:
    """把 PDF 论文解析成结构化 markdown（标题/摘要/方法/图表/公式）。

    Args:
        pdf_path: 论文 PDF 的绝对路径
        tier: 解析质量 flash/basic/standard/advanced（默认 basic）
    Returns:
        结构化 markdown 文本（写入 loot/, 返回路径+摘要）
    """
    text, meta = parse_paper_file(pdf_path, tier=tier)
    out = OUT_DIR / "parsed" / f"{meta.get('stem','paper')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return json.dumps({"path": str(out), "chars": len(text), "meta": meta}, ensure_ascii=False)


@mcp.tool()
def decompose(paper_text: str, requirement: str = "") -> str:
    """用 LLM 拆解论文，产出可作图信息 + Diagram IR（含 locks）。

    Args:
        paper_text: 论文文本（markdown 或纯文本）
        requirement: 用户作图需求描述（可为空，自动推荐）
    Returns:
        JSON：{paper_type, parts, recommended_figures, figure_irs, notes}
    """
    llm = get_llm()
    result = decompose_paper(llm, paper_text, requirement)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def validate_ir_tool(ir: dict) -> str:
    """校验 Diagram IR 是否合法可渲染（节点/边引用、shape、direction、locks）。

    Args:
        ir: Diagram IR JSON 对象
    Returns:
        JSON：{valid, errors[]}
    """
    errors = validate_ir(ir)
    return json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False)


@mcp.tool()
def audit_ir_tool(ir: dict) -> str:
    """对 Diagram IR 做确定性质量审计，返回 passed 闸门。

    Args:
        ir: Diagram IR JSON 对象
    Returns:
        JSON：{passed, hard_failure_count, warning_count, findings[]}
    """
    return json.dumps(audit_ir(ir), ensure_ascii=False, indent=2)


@mcp.tool()
def render_svg(ir: dict, out_name: str = "figure", scheme: str = "okabe-ito") -> str:
    """把确认后的 Diagram IR 渲染成 SVG 文件。

    Args:
        ir: Diagram IR JSON
        out_name: 输出文件基本名
        scheme: 配色主题 (okabe-ito/nature/ieee/vivid/pastel)
    Returns:
        SVG 文件绝对路径
    """
    out = _out(out_name, "svg")
    render_to_svg(ir, str(out), scheme)
    return str(out)


@mcp.tool()
def render_pptx(ir: dict, out_name: str = "figure", scheme: str = "okabe-ito") -> str:
    """把 Diagram IR 渲染成原生可编辑 PPTX（每个节点一个形状、每条边一根连接线）。

    Args:
        ir: Diagram IR JSON
        out_name: 输出文件基本名
        scheme: 配色主题
    Returns:
        PPTX 文件绝对路径
    """
    out = _out(out_name, "pptx")
    render_to_pptx(ir, str(out), scheme)
    return str(out)


@mcp.tool()
def render_emf(ir: dict, out_name: str = "figure", scheme: str = "okabe-ito") -> str:
    """把 Diagram IR 渲染成 EMF（预览用，需 cairosvg；否则占位+SVG）。

    Args:
        ir: Diagram IR JSON
        out_name: 输出文件基本名
        scheme: 配色主题
    Returns:
        EMF 文件绝对路径
    """
    out = _out(out_name, "emf")
    render_to_emf(ir, str(out), scheme)
    return str(out)


@mcp.tool()
def export_spec(ir: dict) -> str:
    """把 Diagram IR 序列化成带 [LOCKED] 标记的文本（供'人编辑后带锁重生成'）。

    Args:
        ir: Diagram IR JSON
    Returns:
        可读文本，用于确认展示与锁定重生成
    """
    from scifig_mcp.diagram_ir import format_ir_for_regeneration
    return format_ir_for_regeneration(ir)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
