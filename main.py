import os
from pathlib import Path
import html
from src.archive_utils import extract_zip_archive
from src.epub_builder import create_epub_from_html, create_epub_from_txt_files
from src.html_processing import process_html_files, sanitize_title
from src.translation import translate_chapters

# load env vars from dotenv import load_dotenv
from dotenv import load_dotenv

load_dotenv()


def main(
    input: str,
    output: str,
    title: str,
    cover_page: str | None = None,
    translate_to: str | None = None,
    translate_start: int | None = None,
    translate_end: int | None = None,
    use_flex_service_tier: bool = True,
    max_translation_retries: int = 3,
):
    unzipped_path = extract_zip_archive(input, output)
    txt_path = process_html_files(output, unzipped_path)

    epub_output_dir = Path(output) / "epub"
    epub_output_dir.mkdir(parents=True, exist_ok=True)

    html_epub_path = epub_output_dir / f"{sanitize_title(title)} (HTML).epub"
    txt_epub_path = epub_output_dir / f"{sanitize_title(title)} (TXT).epub"

    epub_title = title or "Untitled"

    html_content = f"""
    <h1>{html.escape(epub_title)}</h1>
    <p>This EPUB was generated from a direct HTML string.</p>
    <p>You can replace this with any HTML you want.</p>
    """

    create_epub_from_html(
        title=f"{epub_title} (HTML)",
        output_path=html_epub_path,
        html_content=html_content,
        cover_page=Path(cover_page) if cover_page else None,
    )

    create_epub_from_txt_files(
        title=f"{epub_title} (TXT)",
        output_path=txt_epub_path,
        txt_dir=txt_path,
        cover_page=Path(cover_page) if cover_page else None,
    )

    if translate_to:
        translate_chapters(
            txt_path,
            translate_to,
            start=translate_start,
            end=translate_end,
            use_flex_service_tier=use_flex_service_tier,
            max_retries=max_translation_retries,
        )


if __name__ == "__main__":
    inp = Path("./inputs/archive.zip")
    out = Path("./outputs/Duke Pendragon")
    cover_page = Path("./inputs/61fldt2XcwL._UF1000,1000_QL80_.jpg")

    main(
        str(inp),
        str(out),
        title="Duke Pendragon",
        cover_page=str(cover_page),
        translate_to="arabic",
        translate_start=75,
        translate_end=100,
        max_translation_retries=2,
        use_flex_service_tier=True,
    )
