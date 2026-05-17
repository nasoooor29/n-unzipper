from pathlib import Path
import zipfile
from selectolax.parser import HTMLParser


def main(input: str, output: str):
    # unzip archive to output + "unzipped"
    unzipped_path = Path(output) / "unzipped"
    with zipfile.ZipFile(input, "r") as zip_ref:
        zip_ref.extractall(unzipped_path)
    # go over everything on unzipped_path use selectolax to get first h1 as title clean it,
    # then grab all p tags join by \n and save to output + title + .txt
    # save txt to output / txt / title + .txt

    for file in unzipped_path.glob("**/*.html"):
        with open(file, "r", encoding="utf-8") as f:
            html = f.read()

        parser = HTMLParser(html)
        title = (
            parser.css_first("h1")
            .text()
            .strip()
            .lower()
            .replace("chapter chapter", "chapter")
        )
        content = "\n".join([p.text().strip() for p in parser.css("p")])
        output_file = Path(output) / "txt" / f"{title}.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(title + "\n\n" + content)
        print(f"From {file} extracted title: {title} and saved to {output_file}")

    print(f"total files on unzipped_path: {len(list(unzipped_path.glob('**/*.html')))}")
    print(
        f"total files on output/txt: {len(list((Path(output) / 'txt').glob('**/*.txt')))}"
    )


if __name__ == "__main__":
    inp = Path("./inputs/archive.zip")
    out = Path("./outputs/Duke Pendragon")

    main(str(inp), str(out))
