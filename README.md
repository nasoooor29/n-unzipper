## n-unzipper

Generate EPUBs from a zipped HTML archive and from extracted TXT files.
also it will translate the books to another language using llms.

### Quick Run

```powershell
uv run .\main.py
```

### What It Does

- Extracts `./inputs/archive.zip` to `./outputs/.../unzipped`
- Converts HTML chapters to TXT in `./outputs/.../txt`
- Builds two EPUBs in `./outputs/.../epub`
- Prints book stats (chapters, words, characters)

### Files

- `main.py`: Entry point wiring inputs, outputs, title, and cover
- `src/archive_utils.py`: ZIP extraction
- `src/html_processing.py`: HTML → TXT conversion
- `src/epub_builder.py`: EPUB creation (HTML + TXT)
- `src/stats.py`: Book statistics helpers
