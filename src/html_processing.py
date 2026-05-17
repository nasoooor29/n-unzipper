from pathlib import Path
from selectolax.parser import HTMLParser


def process_html_files(output_path: str | Path, unzipped_path: Path) -> Path:
    output_txt_path = Path(output_path) / "txt"
    for file_path in unzipped_path.glob("**/*.html"):
        html_content = file_path.read_text(encoding="utf-8")
        parser = HTMLParser(html_content)
        title_node = parser.css_first("h1")
        title = title_node.text().strip().lower() if title_node else file_path.stem
        title = sanitize_title(title)
        title = title.replace("chapter chapter", "chapter")
        content = "\n".join([p.text().strip() for p in parser.css("p")])
        output_file = output_txt_path / f"{title}.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(title + "\n\n" + content, encoding="utf-8")
        print(f"From {file_path} extracted title: {title} and saved to {output_file}")

    print(f"total files on unzipped_path: {len(list(unzipped_path.glob('**/*.html')))}")
    print(
        f"total files on output/txt: {len(list((Path(output_path) / 'txt').glob('**/*.txt')))}"
    )
    return output_txt_path


def sanitize_title(title: str) -> str:
    return (
        title.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )
