"""vision 模块测试（monkeypatch _chat，不依赖远程模型存活）。"""

import pytest

from scifig_mcp.tools import vision
from scifig_mcp.tools.vision import figure_qa, vision_describe

SAMPLE = {
    "title": "图1 框架",
    "direction": "LR",
    "groups": [],
    "lanes": [],
    "nodes": [
        {"id": "n1", "label": "数据", "shape": "cylinder"},
        {"id": "n2", "label": "模型", "shape": "box"},
    ],
    "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
    "locks": {"nodes": [], "edges": [], "groups": []},
}

FAKE = {"answer": "无问题。", "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


def test_figure_qa_writes_png_and_returns_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(vision, "_chat", lambda messages: FAKE)
    out = figure_qa(SAMPLE, out_dir=str(tmp_path), out_name="fig")
    assert out["ok"] is True
    assert out["answer"] == "无问题。"
    assert out["png_path"].endswith("fig_qa.png")
    import os
    assert os.path.exists(out["png_path"])
    assert os.path.getsize(out["png_path"]) > 1000


def test_figure_qa_message_contains_image_and_context(monkeypatch):
    captured = {}

    def fake(messages):
        captured["messages"] = messages
        return FAKE

    monkeypatch.setattr(vision, "_chat", fake)
    figure_qa(SAMPLE, question="方向对吗？", context="这是某金融论文插图")
    msgs = captured["messages"]
    # 第一条是 context，第二条带图
    assert msgs[0]["content"] == "这是某金融论文插图"
    last = msgs[-1]["content"]
    assert last[0]["type"] == "text" and last[0]["text"] == "方向对吗？"
    assert last[1]["type"] == "image_url"
    assert last[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_figure_qa_default_question_used(monkeypatch):
    captured = {}

    def fake(messages):
        captured["messages"] = messages
        return FAKE

    monkeypatch.setattr(vision, "_chat", fake)
    figure_qa(SAMPLE)
    text = captured["messages"][-1]["content"][0]["text"]
    assert "数据流方向" in text and "发表质量" in text


def test_figure_qa_unreachable_raises_runtimeerror(monkeypatch):
    def fake(messages):
        raise ConnectionError("refused")

    monkeypatch.setattr(vision, "_chat", fake)
    with pytest.raises(RuntimeError, match="多模态模型不可用"):
        figure_qa(SAMPLE)


def test_vision_describe_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(vision, "_chat", lambda messages: FAKE)
    with pytest.raises(FileNotFoundError):
        vision_describe(str(tmp_path / "nope.png"))


def test_vision_describe_returns_answer(tmp_path, monkeypatch):
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 500)
    monkeypatch.setattr(vision, "_chat", lambda messages: FAKE)
    out = vision_describe(str(p))
    assert out["ok"] is True
    assert out["answer"] == "无问题。"
    assert out["image_path"] == str(p)
