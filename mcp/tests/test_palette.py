"""配色方案. """

from scifig_mcp.palette import get_scheme, color_names, SCHEMES


def test_schemes_exist():
    assert "okabe-ito" in SCHEMES
    assert set(color_names()) == set(SCHEMES.keys())


def test_scheme_roles():
    sc = get_scheme("okabe-ito")
    for role in ("primary", "secondary", "accent", "text", "border", "arrow"):
        assert role in sc
        assert "fill" in sc[role]


def test_default_is_okabe_ito():
    assert get_scheme() == SCHEMES["okabe-ito"]


def test_unknown_falls_back():
    assert get_scheme("nonsense") == SCHEMES["okabe-ito"]


def test_all_schemes_have_same_roles():
    for name, sc in SCHEMES.items():
        assert set(sc.keys()) == set(SCHEMES["okabe-ito"].keys()), name
