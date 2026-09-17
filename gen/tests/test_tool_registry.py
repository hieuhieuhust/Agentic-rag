from rag.tools.registry import default_registry


def test_default_tools_are_registered():
    assert set(default_registry.names()) == {
        "search_text",
        "search_image",
        "search_table",
        "search_code",
        "search_formula",
        "search_headings",
    }
    assert len(default_registry.schemas()) == 6
