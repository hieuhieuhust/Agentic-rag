"""Package only the gen modules required by each Google Colab worker."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "gen"
OUTPUT = Path(__file__).resolve().parent / "bundles"

COMMON_FILES = (
    "requirements-colab.txt",
    "config/__init__.py",
    "config/constants.py",
    "config/settings.py",
    "infrastructure/__init__.py",
    "infrastructure/supabase_client.py",
    "workers/__init__.py",
    "workers/client.py",
    "workers/colab/__init__.py",
)

WORKERS = {
    "docling": {
        "files": ("workers/colab/docling_worker.py", "processing/__init__.py"),
        "directories": ("processing/docling",),
    },
    "embedding": {
        "files": ("workers/colab/embedding_worker.py",),
        "directories": ("embeddings",),
    },
}


def package_worker(name: str, destination: Path) -> Path:
    spec = WORKERS[name]
    source_files = [GEN / item for item in COMMON_FILES + spec["files"]]
    for directory in spec["directories"]:
        source_files.extend((GEN / directory).rglob("*.py"))

    missing = [str(path) for path in source_files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing source files: " + ", ".join(missing))

    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"{name}_bundle.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for path in sorted(source_files):
            bundle.write(path, arcname=(Path("gen") / path.relative_to(GEN)).as_posix())
    return archive


if __name__ == "__main__":
    for worker_name in WORKERS:
        print(package_worker(worker_name, OUTPUT))
