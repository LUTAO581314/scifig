"""面向 ChatGPT 的论文到科研图工作流。

SciFig 的高层协议只负责编排和质量闸门，具体解析、规划、渲染和视觉质检
都通过 :class:`PluginRegistry` 注入。这样可以把 MinerU、Docling、ELK、
draw.io、PptxGenJS 或任意 OpenAI-compatible 多模态服务接到同一个 MCP 接口。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from scifig_mcp.diagram_ir import validate_ir
from scifig_mcp.plugins import PluginRegistry, default_registry


class FigureWorkflow:
    """解析 → 规划 → 审计 → 确认后渲染 → 视觉质检的确定性编排器。"""

    def __init__(self, registry: Optional[PluginRegistry] = None):
        self.registry = registry or default_registry()

    def prepare(
        self,
        document_path: str,
        requirement: str = "",
        tier: str = "basic",
        visual: bool = True,
        artifact_dir: Optional[str] = None,
        planner_mode: str = "mcp",
        vision_mode: str = "codex",
        evidence_limit: int = 30000,
    ) -> Dict[str, Any]:
        """准备证据或草稿，永远不会在此阶段生成最终图。

        ``planner_mode=codex`` 只做文档解析和视觉证据提取，把 Diagram IR
        的规划交给调用方（通常是 Codex）；``planner_mode=mcp`` 保留旧行为，
        由注册表里的规划插件调用外部文本模型。
        """
        if planner_mode not in {"codex", "mcp"}:
            raise ValueError("planner_mode 必须是 codex 或 mcp")
        if vision_mode not in {"codex", "mcp", "off"}:
            raise ValueError("vision_mode 必须是 codex、mcp 或 off")

        # Codex 模式只让 MCP 做本地解析，避免子进程偷偷调用外部视觉模型。
        parser_visual = visual and vision_mode == "mcp"
        try:
            text, meta = self.registry.document_parser(
                document_path, tier, parser_visual, vision_mode=vision_mode,
            )
        except TypeError as exc:
            # 兼容已有的三参数外部解析插件。
            if "vision_mode" not in str(exc):
                raise
            text, meta = self.registry.document_parser(
                document_path, tier, parser_visual,
            )

        if visual and vision_mode == "codex":
            from scifig_mcp.tools.parse import collect_visual_evidence

            evidence_dir = Path(artifact_dir or "./loot") / "visual"
            try:
                meta = dict(meta or {})
                meta["visual"] = collect_visual_evidence(
                    document_path, str(evidence_dir),
                )
            except Exception as exc:
                meta = dict(meta or {})
                meta["visual"] = {
                    "enabled": True,
                    "mode": "codex",
                    "status": "error",
                    "artifacts": [],
                    "warnings": [str(exc)],
                }
        elif not visual or vision_mode == "off":
            meta = dict(meta or {})
            meta["visual"] = {"enabled": False, "mode": "off", "status": "disabled"}

        parsed_path = None
        if artifact_dir:
            root = Path(artifact_dir)
            root.mkdir(parents=True, exist_ok=True)
            parsed_path = root / f"{meta.get('stem', 'paper')}.md"
            parsed_path.write_text(text, encoding="utf-8")

        if planner_mode == "codex":
            return {
                "status": "evidence",
                "mode": "codex",
                "next": "Codex 根据 parsed_text 和 visual 元数据生成 Diagram IR，然后调用 render_confirmed_figure。",
                "source": {
                    "document_path": str(Path(document_path).resolve()),
                    "parsed_document_path": str(parsed_path) if parsed_path else None,
                    "meta": meta,
                },
                "requirement": requirement,
                "plugins": dict(self.registry.sources),
                "vision_mode": vision_mode,
                "visual_evidence": meta.get("visual", {}),
                "parsed_text": text[:max(1, evidence_limit)],
                "truncated": len(text) > max(1, evidence_limit),
            }

        plan = self.registry.planner(text, requirement)
        if not isinstance(plan, dict):
            raise ValueError("规划插件必须返回 JSON 对象")

        figures: List[Dict[str, Any]] = []
        for index, ir in enumerate(plan.get("figure_irs", []) or [], start=1):
            validation_errors = validate_ir(ir)
            validation = {"valid": not validation_errors, "errors": validation_errors}
            audit = self.registry.auditor(ir) if validation["valid"] else {
                "passed": False,
                "hard_failure_count": len(validation["errors"]),
                "warning_count": 0,
                "findings": [
                    {"category": "invalid-ir", "severity": "hard", "message": e}
                    for e in validation["errors"]
                ],
            }
            figures.append({
                "index": index,
                "title": ir.get("title", f"Figure {index}"),
                "ir": ir,
                "validation": validation,
                "audit": audit,
                "renderable": bool(validation["valid"] and audit.get("passed")),
            })

        return {
            "status": "draft",
            "mode": "mcp",
            "next": "选择一个 figure_irs 项并确认后调用 render_confirmed_figure；草稿阶段不会交付最终图。",
            "source": {
                "document_path": str(Path(document_path).resolve()),
                "parsed_document_path": str(parsed_path) if parsed_path else None,
                "meta": meta,
            },
            "plugins": dict(self.registry.sources),
            "requirement": requirement,
            "paper_type": plan.get("paper_type"),
            "parts": plan.get("parts", []),
            "recommended_figures": plan.get("recommended_figures", []),
            "figures": figures,
            "notes": plan.get("notes", ""),
        }

    def render_confirmed(
        self,
        ir: Dict[str, Any],
        confirmed: bool,
        out_dir: str,
        out_name: str = "figure",
        formats: Optional[Iterable[str]] = None,
        scheme: str = "okabe-ito",
        qa: bool = True,
        qa_mode: str = "codex",
        question: str = "",
        context: str = "",
    ) -> Dict[str, Any]:
        """只在明确确认且审计通过后渲染，并返回可编辑产物和建议。"""
        if qa_mode not in {"codex", "mcp", "off"}:
            raise ValueError("qa_mode 必须是 codex、mcp 或 off")
        validation_errors = validate_ir(ir)
        audit = self.registry.auditor(ir) if not validation_errors else {
            "passed": False,
            "hard_failure_count": len(validation_errors),
            "warning_count": 0,
            "findings": [
                {"category": "invalid-ir", "severity": "hard", "message": e}
                for e in validation_errors
            ],
        }
        if not confirmed:
            return {
                "status": "awaiting_confirmation",
                "confirmed": False,
                "plugins": dict(self.registry.sources),
                "audit": audit,
                "message": "请先确认这份 Diagram IR；确认后再生成最终图。",
            }
        if validation_errors or not audit.get("passed", False):
            return {
                "status": "blocked",
                "confirmed": True,
                "plugins": dict(self.registry.sources),
                "audit": audit,
                "message": "IR 未通过质量闸门，已阻止交付。请根据 findings 修改后重试。",
            }

        root = Path(out_dir)
        root.mkdir(parents=True, exist_ok=True)
        requested = _normalize_formats(formats)
        outputs: Dict[str, str] = {}
        for fmt in requested:
            path = root / f"{out_name}.{fmt}"
            renderer = getattr(self.registry, f"render_{fmt}", None)
            if renderer is None:
                raise ValueError(f"未注册 {fmt} 渲染插件")
            renderer(ir, str(path), scheme)
            outputs[fmt] = str(path)

        qa_result: Dict[str, Any] = {"status": "skipped"}
        if qa and qa_mode == "codex":
            qa_result = {
                "status": "delegated",
                "mode": "codex",
                "message": "渲染结果已生成；请由 Codex 多模态能力检查 PNG/PDF 后给出视觉修改意见。",
            }
        elif qa and qa_mode == "mcp" and self.registry.vision_qa:
            try:
                qa_result = self.registry.vision_qa(
                    ir, question=question, context=context, scheme=scheme,
                    out_dir=str(root), out_name=out_name,
                )
                qa_result = {"status": "ok", **qa_result}
            except Exception as exc:
                # 渲染产物仍然可交付；把模型配置/服务故障转成可操作建议。
                qa_result = {"status": "unavailable", "error": str(exc)}

        return {
            "status": "complete",
            "confirmed": True,
            "plugins": dict(self.registry.sources),
            "audit": audit,
            "outputs": outputs,
            "qa": qa_result,
            "suggestions": _suggestions(audit, qa_result),
            "ir": ir,
        }


def _normalize_formats(formats: Optional[Iterable[str]]) -> List[str]:
    if formats is None:
        return ["svg", "pptx", "png"]
    if isinstance(formats, str):
        formats = [formats]
    allowed = {"svg", "pptx", "emf", "png", "pdf"}
    result: List[str] = []
    for item in formats:
        value = str(item).lower().lstrip(".")
        if value not in allowed:
            raise ValueError(f"不支持的输出格式: {item}（支持 svg/pptx/emf/png/pdf）")
        if value not in result:
            result.append(value)
    return result or ["svg", "pptx", "png"]


def _suggestions(audit: Dict[str, Any], qa: Dict[str, Any]) -> List[str]:
    suggestions = [
        finding.get("message", "")
        for finding in audit.get("findings", [])
        if finding.get("severity") == "warning"
    ]
    if qa.get("status") == "unavailable":
        suggestions.append("视觉质检未执行：请配置支持图片输入的 SCIFIG_VISION_BASE/KEY/MODEL。")
    answer = qa.get("answer")
    if answer:
        suggestions.append("多模态质检建议：" + str(answer))
    return suggestions


def workflow_json(value: Dict[str, Any]) -> str:
    """MCP 层统一使用的 JSON 序列化。"""
    return json.dumps(value, ensure_ascii=False, indent=2)
