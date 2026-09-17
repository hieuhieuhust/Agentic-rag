"""Bảo đảm snapshot trong gen không làm thất lạc logic Python cũ."""

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_ROOT = PROJECT_ROOT / "gen" / "legacy_runtime"

LEGACY_FILES = (
    "app_ui.py",
    "bridge_module.py",
    "database_manager.py",
    "tab_db_worker.py",
    "tab_docling_worker.py",
    "tab_embedding_worker.py",
    "tab_llm_worker.py",
    "tab_qwen_worker.py",
)


def _normalized_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    source = re.sub(
        r'^SUPABASE_URL\s*=.*$',
        'SUPABASE_URL = "<CONFIGURED_FROM_ENV>"',
        source,
        flags=re.MULTILINE,
    )
    return re.sub(
        r'^SUPABASE_KEY\s*=.*$',
        'SUPABASE_KEY = "<CONFIGURED_FROM_ENV>"',
        source,
        flags=re.MULTILINE,
    )


def test_all_legacy_python_logic_is_snapshotted_inside_gen():
    for filename in LEGACY_FILES:
        source = PROJECT_ROOT / filename
        snapshot = SNAPSHOT_ROOT / filename

        assert source.exists(), f"Thiếu file nguồn cũ: {filename}"
        assert snapshot.exists(), f"Thiếu snapshot trong gen: {filename}"
        assert _normalized_source(snapshot) == _normalized_source(source), (
            f"Snapshot {filename} không còn giống logic nguồn cũ"
        )
