"""SciFig MCP server：论文解析 → 拆解 → 可编辑矢量科研图(SVG/EMF)。

工具清单：
- parse_paper    : PDF → 结构化 markdown（可选，复用 MinerU）
- decompose      : 论文文本 + 需求 → figure_spec JSON（LLM 拆解）
- render_svg     : figure_spec → SVG 文件
- render_emf     : figure_spec → EMF 文件（PPT/Word 直接可编辑）
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastmcp import FastMCP

from scifig_mcp.llm.provider import get_llm
from scifig_mcp.tools.decompose import decompose_paper
from scifig_mcp.tools.parse import parse_paper_file
from scifig_mcp.tools.render import render_to_svg, render_to_emf

mcp = FastMCP("scifig-mcp")

OUT_DIR = Path(os.environ.get("SCIFIG_OUT_DIR", "./loot")).resolve()


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
    """用 LLM 拆解论文，产出可作图信息(figure_spec JSON 及推荐图清单)。

    Args:
        paper_text: 论文文本（markdown 或纯文本）
        requirement: 用户作图需求描述（可为空，自动推荐）
    Returns:
        JSON：{paper_type, parts, recommended_figures, figure_spec}
    """
    llm = get_llm()
    result = decompose_paper(llm, paper_text, requirement)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def render_svg(figure_spec: dict, out_name: str = "figure") -> str:
    """把确认后的 figure_spec 渲染成 SVG 文件。

    Args:
        figure_spec: 拆解阶段输出的作图规格 JSON
        out_name: 输出文件基本名（不含扩展名）
    Returns:
        SVG 文件绝对路径
    """
    out = OUT_DIR / f"{out_name}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_to_svg(figure_spec, str(out))
    return str(out)


@mcp.tool()
def render_emf(figure_spec: dict, out_name: str = "figure") -> str:
    """把 figure_spec 渲染成 EMF 文件（PPT/Word 直接插入即可编辑）。

    Args:
        figure_spec: 拆解阶段输出的作图规格 JSON
        out_name: 输出文件基本名（不含扩展名）
    Returns:
        EMF 文件绝对路径
    """
    out = OUT_DIR / f"{out_name}.emf"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_to_emf(figure_spec, str(out))
    return str(out)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
