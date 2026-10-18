"""SciFig 的插件边界。

核心工作流只依赖这些可替换的函数，具体能力由现成仓库或本地实现提供：
文档解析、多模态理解、布局、渲染和质量检查都可以替换，而不修改 MCP 层。
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Iterable, Optional


DocumentParser = Callable[[str, str, bool], tuple[str, dict]]
# 规划器接收已经解析好的论文文本和用户需求；LLM 的选择由适配器负责。
Planner = Callable[[str, str], dict]
Auditor = Callable[[dict], dict]
Renderer = Callable[[dict, str, str], str]
VisionQA = Callable[..., dict]


@dataclass
class PluginRegistry:
    """工作流使用的能力注册表。

    每个字段都可以替换成外部插件适配器，例如 Docling、ELK、draw.io
    或第三方 PPTX/SVG 渲染器。默认实现仍使用当前仓库的 Python 工具。
    """

    document_parser: DocumentParser
    planner: Planner
    auditor: Auditor
    render_svg: Renderer
    render_pptx: Renderer
    render_emf: Renderer
    vision_qa: Optional[VisionQA] = None
    render_png: Optional[Renderer] = None
    render_pdf: Optional[Renderer] = None
    # 记录实现来源，便于审计、调试和在交付结果中说明实际使用的插件。
    sources: Dict[str, str] = field(default_factory=dict)

    def override(self, **plugins: Any) -> "PluginRegistry":
        """返回带覆盖实现的新注册表，不修改当前工作流。"""
        source = str(plugins.pop("_source", "external"))
        unknown = set(plugins) - {
            "document_parser", "planner", "auditor", "render_svg",
            "render_pptx", "render_emf", "render_png", "render_pdf", "vision_qa",
        }
        if unknown:
            raise ValueError(f"未知插件槽位: {', '.join(sorted(unknown))}")
        source_map = dict(self.sources)
        for name in plugins:
            source_map[name] = source
        return replace(self, sources=source_map, **plugins)


def default_registry() -> PluginRegistry:
    """构造默认插件注册表，采用延迟导入以保持低级工具可独立运行。"""
    from scifig_mcp.tools.audit import audit_ir
    from scifig_mcp.tools.decompose import decompose_paper
    from scifig_mcp.tools.parse import parse_document_file
    from scifig_mcp.tools.render import (
        render_to_emf, render_to_pdf, render_to_png, render_to_pptx, render_to_svg,
    )
    from scifig_mcp.tools.vision import figure_qa
    from scifig_mcp.llm.provider import get_llm

    def planner(paper_text: str, requirement: str) -> dict:
        return decompose_paper(get_llm(), paper_text, requirement)

    return PluginRegistry(
        document_parser=parse_document_file,
        planner=planner,
        auditor=audit_ir,
        render_svg=render_to_svg,
        render_pptx=render_to_pptx,
        render_emf=render_to_emf,
        vision_qa=figure_qa,
        render_png=render_to_png,
        render_pdf=render_to_pdf,
        sources={
            "document_parser": "scifig_mcp.tools.parse.parse_document_file",
            "planner": "scifig_mcp.tools.decompose.decompose_paper",
            "auditor": "scifig_mcp.tools.audit.audit_ir",
            "render_svg": "scifig_mcp.tools.render.render_to_svg",
            "render_pptx": "scifig_mcp.tools.render.render_to_pptx",
            "render_emf": "scifig_mcp.tools.render.render_to_emf",
            "render_png": "scifig_mcp.tools.render.render_to_png",
            "render_pdf": "scifig_mcp.tools.render.render_to_pdf",
            "vision_qa": "scifig_mcp.tools.vision.figure_qa",
        },
    )


def load_registry(
    module_names: Optional[Iterable[str]] = None,
    registry: Optional[PluginRegistry] = None,
) -> PluginRegistry:
    """加载默认插件并应用外部适配器。

    外部模块可以提供以下任一协议：

    * ``register_scifig_plugins(registry)``：返回新的注册表或覆盖字典；
    * ``register(registry)``：同上；
    * ``PLUGIN_OVERRIDES``：字段名到可调用实现的字典。

    未传入 ``module_names`` 时读取 ``SCIFIG_PLUGIN_MODULES``，多个模块用逗号
    分隔。外部模块只负责适配成熟仓库，MCP 工作流和 IR 协议保持不变。
    """
    current = registry or default_registry()
    raw_names = list(module_names or [])
    if not raw_names:
        raw_names = [name.strip() for name in os.environ.get(
            "SCIFIG_PLUGIN_MODULES", ""
        ).split(",") if name.strip()]

    for module_name in raw_names:
        module = importlib.import_module(module_name)
        hook = getattr(module, "register_scifig_plugins", None)
        if hook is None:
            hook = getattr(module, "register", None)
        if hook is not None:
            result = hook(current)
        else:
            result = getattr(module, "PLUGIN_OVERRIDES", None)
        if result is None:
            continue
        if isinstance(result, PluginRegistry):
            current = result
            current.sources = {
                **current.sources,
                "registry": module_name,
            }
            continue
        if not isinstance(result, dict):
            raise TypeError(
                f"插件模块 {module_name} 必须返回 PluginRegistry、覆盖字典或 None"
            )
        current = current.override(_source=module_name, **result)
    return current
