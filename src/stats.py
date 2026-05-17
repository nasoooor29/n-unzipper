from dataclasses import dataclass
from pathlib import Path
import re
from selectolax.parser import HTMLParser


@dataclass
class BookStats:
    chapters: int
    words: int
    characters: int


def count_words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def text_from_html(html_content: str) -> str:
    parser = HTMLParser(html_content)
    return parser.text()


def stats_from_text(text: str, chapters: int) -> BookStats:
    return BookStats(
        chapters=chapters,
        words=count_words(text),
        characters=len(text),
    )


def stats_from_html(html_content: str, chapters: int = 1) -> BookStats:
    text = text_from_html(html_content)
    return stats_from_text(text, chapters)


def stats_from_txt_dir(txt_dir: Path) -> BookStats:
    total_words = 0
    total_chars = 0
    chapter_count = 0
    for txt_file in txt_dir.glob("*.txt"):
        chapter_count += 1
        content = txt_file.read_text(encoding="utf-8")
        total_chars += len(content)
        total_words += count_words(content)
    return BookStats(chapters=chapter_count, words=total_words, characters=total_chars)


def print_book_stats(label: str, stats: BookStats) -> None:
    print(
        f"Stats for {label}: chapters={stats.chapters}, words={stats.words}, characters={stats.characters}"
    )
