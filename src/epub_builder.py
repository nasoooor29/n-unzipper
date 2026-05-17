from pathlib import Path
import html
from ebooklib import epub
from .stats import print_book_stats, stats_from_html, stats_from_txt_dir


def create_epub_from_html(
    title: str, output_path: Path, html_content: str, cover_page: Path | None
) -> None:
    book = epub.EpubBook()
    book.set_identifier("direct-html")
    book.set_title(title)
    book.set_language("en")

    if cover_page and cover_page.exists():
        book.set_cover(cover_page.name, cover_page.read_bytes())

    chapter = epub.EpubHtml(title=title, file_name="chapter_1.xhtml", lang="en")
    chapter.content = html_content

    book.add_item(chapter)
    book.toc = [chapter]
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(output_path), book)
    print(f"Created HTML EPUB: {output_path}")

    stats = stats_from_html(html_content, chapters=1)
    print_book_stats(title, stats)


def create_epub_from_txt_files(
    title: str, output_path: Path, txt_dir: Path, cover_page: Path | None
) -> None:
    book = epub.EpubBook()
    book.set_identifier("txt-files")
    book.set_title(title)
    book.set_language("en")

    if cover_page and cover_page.exists():
        book.set_cover(cover_page.name, cover_page.read_bytes())

    chapters = []
    for txt_file in sorted(txt_dir.glob("*.txt"), key=_chapter_sort_key):
        chapter_title, chapter_html = _txt_file_to_html(txt_file)
        chapter = epub.EpubHtml(
            title=chapter_title, file_name=f"{txt_file.stem}.xhtml", lang="en"
        )
        chapter.content = chapter_html
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = list(chapters)
    book.spine = ["nav", *chapters]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(output_path), book)
    print(f"Created TXT EPUB: {output_path}")

    stats = stats_from_txt_dir(txt_dir)
    print_book_stats(title, stats)


def _txt_file_to_html(txt_file: Path) -> tuple[str, str]:
    content = txt_file.read_text(encoding="utf-8").splitlines()
    if content:
        title = content[0].strip() or txt_file.stem
        body_lines = content[1:]
    else:
        title = txt_file.stem
        body_lines = []

    paragraphs = []
    buffer = []
    for line in body_lines:
        if line.strip():
            buffer.append(line.strip())
        else:
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
    if buffer:
        paragraphs.append(" ".join(buffer))

    paragraph_html = "".join(
        f"<p>{html.escape(p)}</p>" for p in paragraphs if p
    )
    return title, f"<h1>{html.escape(title)}</h1>{paragraph_html}"


def _chapter_sort_key(path: Path) -> tuple[int, str]:
    name = path.stem
    parts = name.split()
    for part in reversed(parts):
        if part.isdigit():
            return int(part), name
    return 10**9, name
