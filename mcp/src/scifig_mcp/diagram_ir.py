"""Diagram IR：拆解确认的核心中间表示（基于 paperbanana 的设计，结合可编辑目标）。

IR 不存绝对坐标（由渲染器计算布局），而是表达拓扑结构 + 分组泳道 + 布局方向，
再加 locks 机制实现"人编辑后带锁定重新生成"的可编辑闭环。

Schema:
{
  "title": "图1 系统框架",
  "direction": "LR|TB",
  "groups": [{"id": "g1", "label": "输入层"}],
  "lanes": [{"id": "l1", "label": "阶段 A"}],          # 可选泳道
  "nodes": [{"id": "n1", "label": "预处理", "group": "g1",
             "lane": "l1", "shape": "round|box|diamond|cylinder|ellipse"}],
  "edges": [{"id": "e1", "source": "n1", "target": "n2",
             "label": "特征", "style": "solid|dashed|feedback"}],
  "legend": [{"label": "主流程", "style": "solid"}],
  "layout": {"row_scale": 0.68},
  "locks": {"nodes": ["n1"], "edges": ["e1"], "groups": []}
}
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

# 有效取值的强约束（渲染与校验共用）
SHAPES = {"round", "box", "diamond", "cylinder", "ellipse", "parallelogram", "cloud"}
DIRECTIONS = {"LR", "TB", "RL", "BT"}
EDGE_STYLES = {"solid", "dashed", "feedback"}


def validate_ir(ir: Dict[str, Any]) -> List[str]:
    """校验 IR，返回错误列表（空 = 合法可渲染）。"""
    errors: List[str] = []

    if not isinstance(ir, dict):
        return ["IR 必须是对象"]

    nodes = ir.get("nodes", [])
    edges = ir.get("edges", [])
    groups = ir.get("groups", [])

    direction = ir.get("direction", "LR")
    if direction not in DIRECTIONS:
        errors.append(f"无效 direction: {direction}")

    node_ids = []
    for i, nd in enumerate(nodes):
        nid = nd.get("id")
        if not nid:
            errors.append(f"nodes[{i}] 缺 id")
            continue
        if nid in node_ids:
            errors.append(f"节点 id 重复: {nid}")
        node_ids.append(nid)
        shape = nd.get("shape", "round")
        if shape not in SHAPES:
            errors.append(f"节点 {nid} 非法 shape: {shape}")
        position = nd.get("position")
        if position is not None:
            if not isinstance(position, dict) or "x" not in position or "y" not in position:
                errors.append(f"节点 {nid} 的 position 必须包含 x/y")
            else:
                try:
                    float(position["x"])
                    float(position["y"])
                except (TypeError, ValueError):
                    errors.append(f"节点 {nid} 的 position x/y 必须是数字")

    group_ids = {g.get("id") for g in groups}

    # 边引用必须存在
    edge_ids = []
    for i, e in enumerate(edges):
        eid = e.get("id")
        if eid:
            if eid in edge_ids:
                errors.append(f"边 id 重复: {eid}")
            edge_ids.append(eid)
        if e.get("source") not in node_ids:
            errors.append(f"边 {e.get('id', i)} 引用不存在的 source: {e.get('source')}")
        if e.get("target") not in node_ids:
            errors.append(f"边 {e.get('id', i)} 引用不存在的 target: {e.get('target')}")
        st = e.get("style", "solid")
        if st not in EDGE_STYLES:
            errors.append(f"边 {e.get('id', i)} 非法 style: {st}")

    # group 引用必须存在
    for g in groups:
        for nid in g.get("node_ids", []):
            if nid not in node_ids:
                errors.append(f"组 {g.get('id')} 引用不存在节点: {nid}")

    # locks 引用必须存在
    locks = ir.get("locks", {})
    for nid in locks.get("nodes", []):
        if nid not in node_ids:
            errors.append(f"locks.nodes 引用不存在节点: {nid}")
    for eid in locks.get("edges", []):
        if eid and eid not in edge_ids:
            errors.append(f"locks.edges 引用不存在边: {eid}")
    for gid in locks.get("groups", []):
        if gid not in group_ids:
            errors.append(f"locks.groups 引用不存在组: {gid}")

    return errors


def is_valid_ir(ir: Dict[str, Any]) -> bool:
    return not validate_ir(ir)


def format_ir_for_regeneration(ir: Dict[str, Any]) -> str:
    """把 IR 序列化为带 [LOCKED] 标记的文本，用于"人编辑后带锁重生成"。"""
    locked_nodes = set(ir.get("locks", {}).get("nodes", []))
    locked_edges = set(ir.get("locks", {}).get("edges", []))
    locked_groups = set(ir.get("locks", {}).get("groups", []))

    lines: List[str] = []
    lines.append(f"Title: {ir.get('title', '')}")
    lines.append(f"Direction: {ir.get('direction', 'LR')}")

    if ir.get("groups"):
        lines.append("Groups:")
        for g in ir["groups"]:
            tag = " [LOCKED]" if g.get("id") in locked_groups else ""
            lines.append(f"  - {g.get('id')}: {g.get('label')}{tag}")

    if ir.get("lanes"):
        lines.append("Lanes:")
        for lane in ir["lanes"]:
            lines.append(f"  - {lane.get('id')}: {lane.get('label')}")

    lines.append("Nodes:")
    for nd in ir.get("nodes", []):
        tag = " [LOCKED]" if nd.get("id") in locked_nodes else ""
        lane = f" lane={nd.get('lane')}" if nd.get("lane") else ""
        g = f" group={nd.get('group')}" if nd.get("group") else ""
        pos = nd.get("position")
        position = f" position=({pos.get('x')},{pos.get('y')})" if pos else ""
        lines.append(
            f"  - {nd.get('id')}: {nd.get('label')} "
            f"[shape={nd.get('shape', 'round')}]{g}{lane}{position}{tag}"
        )

    lines.append("Edges:")
    for e in ir.get("edges", []):
        tag = " [LOCKED]" if e.get("id") in locked_edges else ""
        lbl = f" label={e.get('label')}" if e.get("label") else ""
        st = f" style={e.get('style', 'solid')}"
        lines.append(f"  - {e.get('source')} -> {e.get('target')}{lbl}{st}{tag}")

    return "\n".join(lines)


def ir_to_json(ir: Dict[str, Any]) -> str:
    return json.dumps(ir, ensure_ascii=False, indent=2)
