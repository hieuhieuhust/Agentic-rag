import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def function_dumps(source: str) -> list[str]:
    return [
        ast.dump(node, include_attributes=False)
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef)
    ]


def notebook_cell(notebook: dict, index: int) -> str:
    return "".join(notebook["cells"][index]["source"])


def test_mechanical_function_extraction_is_unchanged():
    notebook = json.loads((ROOT.parent / "docling.ipynb").read_text(encoding="utf-8"))
    groups = {
        "heading_extractor.py": [11, 13, 15, 17],
        "toc_analyzer.py": [23, 25, 27, 29, 35],
        "hierarchy_builder.py": [31, 33, 41, 43, 45, 47, 49],
        "element_processor.py": [51, 53, 55, 57, 59],
    }
    for filename, indexes in groups.items():
        expected = [
            function
            for index in indexes
            for function in function_dumps(notebook_cell(notebook, index))
        ]
        actual = function_dumps(
            (ROOT / "processing" / "docling" / filename).read_text(encoding="utf-8")
        )
        assert actual == expected


def test_find_heading_is_unchanged():
    notebook = json.loads((ROOT.parent / "docling.ipynb").read_text(encoding="utf-8"))
    expected = function_dumps(notebook_cell(notebook, 61))[0]
    functions = function_dumps(
        (ROOT / "processing" / "docling" / "pipeline.py").read_text(
            encoding="utf-8"
        )
    )
    assert functions[0] == expected


def test_postprocessing_functions_are_unchanged():
    notebook = json.loads((ROOT.parent / "docling.ipynb").read_text(encoding="utf-8"))
    source_functions = {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.parse(notebook_cell(notebook, 63)).body
        if isinstance(node, ast.FunctionDef)
    }
    targets = {
        "context_enricher.py": {
            "filter_elements_after_toc",
            "assign_heading_paths",
            "assign_context_snippets",
        },
        "table_processor.py": {"extract_full_table_text"},
        "image_processor.py": {"crop_and_upload_images"},
        "chunk_builder.py": {"package_chunks"},
    }
    for filename, names in targets.items():
        target_source = (
            ROOT / "processing" / "docling" / filename
        ).read_text(encoding="utf-8")
        actual = {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(target_source).body
            if isinstance(node, ast.FunctionDef)
        }
        assert actual == {name: source_functions[name] for name in names}
