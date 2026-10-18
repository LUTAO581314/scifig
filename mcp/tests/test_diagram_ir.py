"""核心数据结构：Diagram IR 校验与锁定序列化. """

from scifig_mcp.diagram_ir import validate_ir, is_valid_ir, format_ir_for_regeneration

VALID_IR = {
    "title": "图1",
    "direction": "LR",
    "groups": [{"id": "g1", "label": "输入"}],
    "lanes": [{"id": "l1", "label": "阶段A"}],
    "nodes": [
        {"id": "n1", "label": "模块A", "group": "g1", "lane": "l1", "shape": "round"},
        {"id": "n2", "label": "模块B", "group": "g1", "shape": "box"},
    ],
    "edges": [{"id": "e1", "source": "n1", "target": "n2", "label": "流", "style": "solid"}],
    "locks": {"nodes": ["n1"], "edges": [], "groups": []},
}


def test_valid_ir():
    assert is_valid_ir(VALID_IR)
    assert validate_ir(VALID_IR) == []


def test_edge_ref_missing_node():
    ir = {**VALID_IR, "edges": [{"id": "x", "source": "n1", "target": "ghost"}]}
    assert not is_valid_ir(ir)
    assert any("ghost" in e for e in validate_ir(ir))


def test_duplicate_node_id():
    ir = {
        "nodes": [
            {"id": "n1", "label": "a"},
            {"id": "n1", "label": "b"},
        ],
        "edges": [],
    }
    assert not is_valid_ir(ir)


def test_invalid_shape():
    ir = {**VALID_IR, "nodes": [{"id": "n9", "label": "x", "shape": "star"}]}
    assert not is_valid_ir(ir)


def test_invalid_direction():
    ir = {**VALID_IR, "direction": "DIAG"}
    assert not is_valid_ir(ir)


def test_lock_ref_missing():
    ir = {**VALID_IR, "locks": {"nodes": ["notexist"]}}
    assert not is_valid_ir(ir)


def test_format_marks_locked():
    s = format_ir_for_regeneration(VALID_IR)
    assert "[LOCKED]" in s
    assert "n1" in s


def test_format_locked_specific():
    ir = {**VALID_IR, "locks": {"nodes": ["n2"], "edges": [], "groups": ["g1"]}}
    s = format_ir_for_regeneration(ir)
    # n2 与 g1 应被标记 LOCKED，n1 不应
    lines_n2 = [line for line in s.splitlines() if "n2:" in line]
    assert lines_n2 and "[LOCKED]" in lines_n2[0]
    lines_n1 = [line for line in s.splitlines() if "n1:" in line]
    assert lines_n1 and "[LOCKED]" not in lines_n1[0]
    lines_g1 = [line for line in s.splitlines() if "g1:" in line]
    assert lines_g1 and "[LOCKED]" in lines_g1[0]


def test_manual_position_requires_numeric_xy():
    ir = {"nodes": [{"id": "n1", "position": {"x": "left", "y": 20}}]}

    assert any("position x/y" in error for error in validate_ir(ir))
