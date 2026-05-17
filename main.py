from pathlib import Path
import zipfile
from selectolax.parser import HTMLParser


def main(input: str, output: str):
    unzipped_path = extract_zip_archive(input, output)
    txt_path = process_html_files(output, unzipped_path)
    # convert_to_epub(output, txt_path)


def process_html_files(output, unzipped_path):
    # go over everything on unzipped_path use selectolax to get first h1 as title clean it,
    # then grab all p tags join by \n and save to output + title + .txt
    # save txt to output / txt / title + .txt
    output_txt_path = Path(output) / "txt"
    for file in unzipped_path.glob("**/*.html"):
        with open(file, "r", encoding="utf-8") as f:
            html = f.read()

        parser = HTMLParser(html)
        title = parser.css_first("h1").text().strip().lower()
        # sanitize title by replacing spaces with underscores and removing special characters
        title = sanitize_title(title)
        title = title.replace("chapter chapter", "chapter")
        content = "\n".join([p.text().strip() for p in parser.css("p")])
        output_file = output_txt_path/ f"{title}.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(title + "\n\n" + content)
        print(f"From {file} extracted title: {title} and saved to {output_file}")

    print(f"total files on unzipped_path: {len(list(unzipped_path.glob('**/*.html')))}")
    print(
        f"total files on output/txt: {len(list((Path(output) / 'txt').glob('**/*.txt')))}"
    )
    return output_txt_path


def sanitize_title(title: str):
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


def extract_zip_archive(input, output):
    # unzip archive to output + "unzipped"
    unzipped_path = Path(output) / "unzipped"
    with zipfile.ZipFile(input, "r") as zip_ref:
        zip_ref.extractall(unzipped_path)
    return unzipped_path


if __name__ == "__main__":
    inp = Path("./inputs/archive.zip")
    out = Path("./outputs/Duke Pendragon")

    main(str(inp), str(out))
