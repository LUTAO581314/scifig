"""统一文本/多模态模型端点配置测试。"""

import pytest

from scifig_mcp.llm.provider import get_model_config


def test_multimodal_config_prefers_vision_over_text(monkeypatch):
    monkeypatch.setenv("SCIFIG_LLM_BASE", "https://text.example/v1")
    monkeypatch.setenv("SCIFIG_LLM_KEY", "text-key")
    monkeypatch.setenv("SCIFIG_LLM_MODEL", "text-model")
    monkeypatch.setenv("SCIFIG_VISION_BASE", "https://vision.example/v1")
    monkeypatch.setenv("SCIFIG_VISION_KEY", "vision-key")
    monkeypatch.setenv("SCIFIG_VISION_MODEL", "vision-model")

    cfg = get_model_config("multimodal")
    assert cfg.base == "https://vision.example/v1"
    assert cfg.key == "vision-key"
    assert cfg.model == "vision-model"


def test_multimodal_config_falls_back_to_llm(monkeypatch):
    monkeypatch.delenv("SCIFIG_VISION_BASE", raising=False)
    monkeypatch.delenv("SCIFIG_VISION_KEY", raising=False)
    monkeypatch.delenv("SCIFIG_VISION_MODEL", raising=False)
    monkeypatch.setenv("SCIFIG_LLM_BASE", "https://shared.example/v1")
    monkeypatch.setenv("SCIFIG_LLM_KEY", "shared-key")
    monkeypatch.setenv("SCIFIG_LLM_MODEL", "vision-capable-model")

    cfg = get_model_config("multimodal")
    assert (cfg.base, cfg.key, cfg.model) == (
        "https://shared.example/v1", "shared-key", "vision-capable-model"
    )


def test_multimodal_config_requires_credentials(monkeypatch):
    for name in (
        "SCIFIG_VISION_BASE", "SCIFIG_VISION_KEY", "SCIFIG_VISION_MODEL",
        "SCIFIG_LLM_BASE", "SCIFIG_LLM_KEY", "SCIFIG_LLM_MODEL",
        "SCIFIG_LLM_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="多模态模型配置"):
        get_model_config("multimodal")


def test_multimodal_config_does_not_guess_text_model(monkeypatch):
    monkeypatch.setenv("SCIFIG_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("SCIFIG_LLM_KEY", "shared-key")
    monkeypatch.delenv("SCIFIG_LLM_BASE", raising=False)
    monkeypatch.delenv("SCIFIG_LLM_MODEL", raising=False)
    monkeypatch.delenv("SCIFIG_VISION_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="多模态模型配置"):
        get_model_config("multimodal")
