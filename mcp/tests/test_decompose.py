"""拆解工具：extract_json 容错解析. """

import pytest

from scifig_mcp.tools.decompose import extract_json


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_fenced_multiline():
    s = "```json\n{\"a\": 1}\n```"
    assert extract_json(s) == {"a": 1}


def test_fenced_inline():
    assert extract_json('```json {"a": 2} ```') == {"a": 2}


def test_wrapped_with_text():
    assert extract_json("here is the result {\"a\": 4} hope it helps") == {"a": 4}


def test_no_json_raises():
    with pytest.raises(ValueError):
        extract_json("no json here at all")


def test_nested_object():
    s = '{"fig": [{"id": "n1", "label": "x"}], "ok": true}'
    d = extract_json(s)
    assert d["fig"][0]["id"] == "n1"
