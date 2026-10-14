"""确定性审计：对生成的科研图做可计算的质量硬校验（借鉴 scientific-illustrator 的 audit_figure）。

审计结果 passed = (hard_failure_count == 0)。用于反驳 LLM"自我感觉良好"，做可验收的质量闸门。
"""

from __future__ import annotations

from typing import Any, Dict, List

from scifig_mcp.diagram_ir import validate_ir
from scifig_mcp.tools.render import NODE_W, NODE_H, _layout


class Finding:
    def __init__(self, category: str, severity: str, message: str):
        self.category = category
        self.severity = severity  # "hard" | "warning"
        self.message = message

    def to_dict(self) -> Dict[str, str]:
        return {"category": self.category, "severity": self.severity, "message": self.message}


def audit_ir(ir: Dict[str, Any]) -> Dict[str, Any]:
    """审计 IR 的可编辑图质量，返回确定性 gate 结果。"""
    findings: List[Finding] = []

    # 1. IR 基本合法性
    for err in validate_ir(ir):
        findings.append(Finding("invalid-ir", "hard", err))

    node_center, _, _, _ = _layout(ir)
    nodes = {n.get("id"): n for n in ir.get("nodes", [])}

    # 2. 节点越界（超出合理画布范围）
    xs = [c[0] for c in node_center.values()]
    ys = [c[1] for c in node_center.values()]
    if xs:
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        span_x = maxx - minx
        span_y = maxy - miny
        if span_x > 4000 or span_y > 2600:
            findings.append(Finding(
                "outside-page", "hard",
                f"节点布局跨度过大（{span_x:.0f}x{span_y:.0f}），需拆分或缩小画布"))

    # 3. 信息密度（CCF-Figure 容量上限）
    n_nodes = len(ir.get("nodes", []))
    n_edges = len(ir.get("edges", []))
    if n_nodes > 7 and n_edges > 10:
        findings.append(Finding(
            "information-overload", "warning",
            f"单图密度偏高({n_nodes}节点/{n_edges}箭头)，建议拆分子图或降级次要模块"))

    # 4. 孤立节点（无任何连线）
    connected = set()
    for e in ir.get("edges", []):
        connected.add(e.get("source"))
        connected.add(e.get("target"))
    for nid in nodes:
        if nid not in connected and len(nodes) > 1:
            findings.append(Finding(
                "isolated-node", "warning", f"节点 {nid} 未与任何边相连"))

    # 5. 空标签节点
    for nid, nd in nodes.items():
        if not nd.get("label"):
            findings.append(Finding("empty-label", "warning", f"节点 {nid} 无标签"))

    # 6. 分组引用一致性
    for g in ir.get("groups", []):
        members = [nd for nd in ir.get("nodes", []) if nd.get("group") == g.get("id")]
        if not members:
            findings.append(Finding("empty-group", "warning", f"组 {g.get('id')} 无成员节点"))

    hard = [f for f in findings if f.severity == "hard"]
    return {
        "passed": len(hard) == 0,
        "hard_failure_count": len(hard),
        "warning_count": len(findings) - len(hard),
        "findings": [f.to_dict() for f in findings],
    }
