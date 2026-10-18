import sys
import types

from scifig_mcp.plugins import PluginRegistry, load_registry


def _base_registry():
    def parser(path, tier, visual):
        return "", {}

    def planner(text, requirement):
        return {}

    def audit(ir):
        return {"passed": True, "findings": []}

    def render(ir, path, scheme):
        return path

    return PluginRegistry(
        document_parser=parser,
        planner=planner,
        auditor=audit,
        render_svg=render,
        render_pptx=render,
        render_emf=render,
    )


def test_external_register_hook_can_replace_plugin(monkeypatch):
    module = types.ModuleType("test_scifig_adapter")

    def custom_renderer(ir, path, scheme):
        return "custom:" + path

    def register(registry):
        return registry.override(render_svg=custom_renderer, _source=__name__)

    module.register_scifig_plugins = register
    monkeypatch.setitem(sys.modules, module.__name__, module)

    registry = load_registry([module.__name__], registry=_base_registry())

    assert registry.render_svg({}, "a.svg", "") == "custom:a.svg"
    assert registry.sources["render_svg"] == __name__


def test_external_override_dictionary_is_supported(monkeypatch):
    module = types.ModuleType("test_scifig_dict_adapter")

    def custom_qa(*args, **kwargs):
        return {"answer": "ok"}

    module.PLUGIN_OVERRIDES = {"vision_qa": custom_qa}
    monkeypatch.setitem(sys.modules, module.__name__, module)

    registry = load_registry([module.__name__], registry=_base_registry())

    assert registry.vision_qa() == {"answer": "ok"}
    assert registry.sources["vision_qa"] == module.__name__
