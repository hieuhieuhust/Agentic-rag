"""Tách cơ học code từ docling.ipynb mà không sửa logic thuật toán."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT.parent / "docling.ipynb"
OUTPUT = ROOT / "processing" / "docling"


def cell_source(notebook: dict, index: int) -> str:
    return "".join(notebook["cells"][index]["source"])


def module_nodes(source: str) -> list[str]:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    selected: list[str] = []
    for node in tree.body:
        if isinstance(
            node,
            (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef),
        ):
            selected.append("".join(lines[node.lineno - 1 : node.end_lineno]))
    return selected


def function_source(source: str, names: set[str]) -> list[str]:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    return [
        "".join(lines[node.lineno - 1 : node.end_lineno])
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]


def write_module(path: Path, sections: list[str], preamble: str = "") -> None:
    header = (
        '"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""\n\n'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        header + preamble + "\n\n".join(section.rstrip() for section in sections) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))

    groups = {
        "heading_extractor.py": [11, 13, 15, 17],
        "toc_analyzer.py": [23, 25, 27, 29, 35],
        "hierarchy_builder.py": [31, 33, 41, 43, 45, 47, 49],
        "element_processor.py": [51, 53, 55, 57, 59],
    }
    for filename, cell_indexes in groups.items():
        sections: list[str] = []
        for index in cell_indexes:
            sections.extend(module_nodes(cell_source(notebook, index)))
        write_module(OUTPUT / filename, sections)

    postprocess = cell_source(notebook, 63)
    write_module(
        OUTPUT / "context_enricher.py",
        function_source(
            postprocess,
            {
                "filter_elements_after_toc",
                "assign_heading_paths",
                "assign_context_snippets",
            },
        ),
    )
    write_module(
        OUTPUT / "table_processor.py",
        function_source(postprocess, {"extract_full_table_text"}),
    )
    write_module(
        OUTPUT / "image_processor.py",
        function_source(postprocess, {"crop_and_upload_images"}),
        preamble="import fitz\nimport os\n\n",
    )
    write_module(
        OUTPUT / "chunk_builder.py",
        function_source(postprocess, {"package_chunks"}),
    )

    pipeline_imports = """\
from processing.docling.element_processor import (
    add_caption_field_to_element_coords,
    convert_monospace_text_to_code,
    fix_tables_misidentified_as_pictures,
    merge_pictures_by_coordinates,
    split_picture_containing_code,
)
from processing.docling.heading_extractor import (
    build_struct_raw,
    dominant_span_info,
    get_bold_headings,
    is_bold,
)
from processing.docling.hierarchy_builder import (
    assign_levels_for_missing_blocks,
    assign_levels_to_struct_merged,
    enrich_font_name,
    filter_monospace_headings,
    filter_suspects_from_elements,
    get_missing_level_blocks,
    resolve_removed_headings,
)
from processing.docling.toc_analyzer import (
    assign_levels_and_build_tree,
    extract_bookmark_tree,
    extract_toc_headings,
    process_toc_v2,
)

"""
    write_module(
        OUTPUT / "pipeline.py",
        module_nodes(cell_source(notebook, 61)),
        preamble=pipeline_imports,
    )


if __name__ == "__main__":
    main()
