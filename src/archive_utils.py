from pathlib import Path
import zipfile


def extract_zip_archive(input_path: str | Path, output_path: str | Path) -> Path:
    unzipped_path = Path(output_path) / "unzipped"
    with zipfile.ZipFile(input_path, "r") as zip_ref:
        zip_ref.extractall(unzipped_path)
    return unzipped_path
