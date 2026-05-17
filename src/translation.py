import asyncio
import os
import re
from pathlib import Path
from typing import Any

from openrouter import OpenRouter

MODEL = "google/gemini-2.5-flash-lite"
MAX_CHARACTER_SHEET_CHARS = 5000
# TARGET_CHARACTER_SHEET_CHARS = 5000
TRANSLATED_START = "<<<TRANSLATED_CHAPTER_START>>>"
TRANSLATED_END = "<<<TRANSLATED_CHAPTER_END>>>"
SHEET_START = "<<<UPDATED_CHARACTER_SHEET_START>>>"
SHEET_END = "<<<UPDATED_CHARACTER_SHEET_END>>>"
COMPACTED_SHEET_START = "<<<COMPACTED_CHARACTER_SHEET_START>>>"
COMPACTED_SHEET_END = "<<<COMPACTED_CHARACTER_SHEET_END>>>"


def _book_root_for(chapter_file: Path) -> Path:
    if chapter_file.parent.name.lower() == "txt":
        return chapter_file.parent.parent
    return chapter_file.parent


def _safe_path_part(value: str) -> str:
    return re.sub(r"[^\w.-]+", "_", value.strip().lower()).strip("_") or "language"


def _default_sheet_path(chapter_file: Path, target_language: str) -> Path:
    return (
        _book_root_for(chapter_file)
        / "characterSheet"
        / _safe_path_part(target_language)
        / "character_sheet.yaml"
    )


def _legacy_default_sheet_path(chapter_file: Path, target_language: str) -> Path:
    return (
        _book_root_for(chapter_file)
        / "characterSheet"
        / _safe_path_part(target_language)
        / "character_sheet.md"
    )


def _output_paths(
    chapter_file: Path, character_sheet_file: Path | None
) -> tuple[Path, Path]:
    book_root = _book_root_for(chapter_file)
    return (
        book_root / "translated" / chapter_file.name,
        character_sheet_file
        if character_sheet_file
        else book_root / "characterSheet" / "character_sheet.yaml",
    )


def _failed_path(chapter_file: Path) -> Path:
    return _book_root_for(chapter_file) / "failed_TL" / f"{chapter_file.stem}.md"


def _split_title(chapter_text: str, chapter_file: Path) -> tuple[str, str]:
    lines = chapter_text.splitlines()
    if not lines:
        return chapter_file.stem, ""
    return lines[0], "\n".join(lines[1:]).lstrip("\n")


def _natural_sort_key(path: Path) -> list[int | str]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.stem)
    ]


def _chapter_slice(
    chapter_files: list[Path], start: int | None, end: int | None
) -> list[Path]:
    start_index = max(start - 1, 0) if start is not None else None
    end_index = end if end is not None else None
    return chapter_files[start_index:end_index]


def _extract_response_text(response: Any) -> str:
    return response.choices[0].message.content or ""


def _between(content: str, start: str, end: str) -> str:
    start_index = content.find(start)
    end_index = content.find(end)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return ""
    return content[start_index + len(start) : end_index].strip()


def _parse_translation_response(content: str) -> tuple[str, str]:
    translated_chapter = _between(content, TRANSLATED_START, TRANSLATED_END)
    updated_character_sheet = _between(content, SHEET_START, SHEET_END)
    if not translated_chapter or not updated_character_sheet:
        raise ValueError(
            "OpenRouter response must include the required translation and sheet markers."
        )
    return translated_chapter, updated_character_sheet


def _parse_compacted_sheet(content: str) -> str:
    compacted = _between(content, COMPACTED_SHEET_START, COMPACTED_SHEET_END)
    if not compacted:
        raise ValueError("OpenRouter response must include the required compaction markers.")
    return compacted.strip() + "\n"


def _save_failed_translation(
    chapter_file: Path, error: Exception, response_text: str | None
) -> Path:
    failed_path = _failed_path(chapter_file)
    failed_path.parent.mkdir(parents=True, exist_ok=True)
    failed_path.write_text(
        f"# Failed Translation\n\n"
        f"- Chapter: `{chapter_file.name}`\n"
        f"- Error: `{type(error).__name__}: {error}`\n\n"
        f"## Raw Response\n\n{response_text or '[no response]'}\n",
        encoding="utf-8",
    )
    return failed_path


def _preserve_original_title(translated_chapter: str, original_title: str) -> str:
    lines = translated_chapter.splitlines()
    if not lines:
        return original_title
    if lines[0] == original_title:
        return translated_chapter.strip() + "\n"
    return "\n".join([original_title, *lines[1:]]).strip() + "\n"


def _build_messages(
    chapter_file: Path,
    target_language: str,
    character_sheet: str,
    chapter_title: str,
    chapter_body: str,
) -> list[dict[str, str]]:
    sheet_instruction = (
        "Use the provided character/reference sheet as the source of truth. Update it "
        "only with important new or changed information from this chapter."
        if character_sheet.strip()
        else "The character/reference sheet is empty. Create a compact YAML master "
        "glossary containing only important character names, country/location names, "
        "power levels, factions, titles, and special story-specific terms from this chapter."
    )

    system_prompt = f"""
You are a literary translator for novels and story chapters.
Translate the chapter into {target_language} while preserving story continuity.

Rules:
- Preserve the first line/chapter title exactly as provided. Do not translate, rewrite, or reformat it.
- Preserve names, relationships, titles, locations, power systems, ranks, countries, factions, and story-specific terminology consistently in the translated chapter.
- Use the character/reference sheet only as a glossary for names, titles, locations, power levels, countries, factions, and special terminology.
- Keep prose natural in {target_language}, but do not summarize or omit content.
- Return exactly two sections using these markers and no other text:
  {TRANSLATED_START}
  full translated chapter
  {TRANSLATED_END}
  {SHEET_START}
  updated character/reference sheet
  {SHEET_END}
- The translated chapter section is message 1 and must contain the full translated chapter, starting with the unchanged original title.
- The updated character/reference sheet section is message 2 and must contain the updated reference sheet.
- updated_character_sheet must be short YAML, not Markdown prose.
- The YAML is only for translation consistency. Sacrifice details to keep it short.
- Use this structure when relevant:
  characters:
    after translation name: original name
  countries:
    after translation name: original name
  power_levels:
    after translation name: original name
  special_words:
    after translation name: original name
- Only add special story-specific terms. Do not add common words that have ordinary dictionary translations.
- Do not add who follows who, who fights who, temporary travel groups, scene events, personality notes, or chapter summaries.
- Do not add roles, notes, relationships, or details unless they are part of a fixed title/name/term needed for consistent translation.
- Keep existing original names stable. If a name/term already exists, reuse it instead of adding a duplicate.
""".strip()

# - Keep the entire YAML easy to skim and preferably under {TARGET_CHARACTER_SHEET_CHARS} characters.
    user_prompt = f"""
{sheet_instruction}

Chapter file name, which must stay unchanged when saved:
{chapter_file.name}

Original chapter title, preserve this exact first line:
{chapter_title}

Current character/reference sheet:
{character_sheet if character_sheet.strip() else "[empty]"}

Chapter body to translate:
{chapter_body}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _build_compaction_messages(
    target_language: str, character_sheet: str
) -> list[dict[str, str]]:
    system_prompt = f"""
You compact novel translation YAML glossaries.

Rules:
- Return only the compacted YAML sheet between these markers:
  {COMPACTED_SHEET_START}
  compacted YAML sheet
  {COMPACTED_SHEET_END}
- Keep only translation-consistency glossary entries, not story notes.
- Use only these top-level categories when relevant: characters, countries, power_levels, special_words.
- Each entry should be a mapping from translated_name to original name.
- Preserve important stable names, titles, locations, factions, power levels, and special terminology.
- Remove common words, minor details, temporary relationships, who follows who, who fights who, scene events, personality notes, and summaries.
- Remove duplicates and merge equivalent entries.
- Prefer sacrificing details over making the sheet long.
""".strip()

# - Keep the compacted YAML under {TARGET_CHARACTER_SHEET_CHARS} characters when possible.

    user_prompt = f"""
Compact this YAML glossary because it is getting too long:

{character_sheet}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def _compact_character_sheet_async(
    open_router: OpenRouter,
    target_language: str,
    character_sheet: str,
    use_flex_service_tier: bool,
) -> str:
    if len(character_sheet) <= MAX_CHARACTER_SHEET_CHARS:
        return character_sheet

    response = await open_router.chat.send_async(
        messages=_build_compaction_messages(target_language, character_sheet),
        model=MODEL,
        provider={"sort": "price"},
        service_tier="flex" if use_flex_service_tier else None,
        temperature=0.1,
    )
    print(f"compaction usage: {response.usage}")
    return _parse_compacted_sheet(_extract_response_text(response))


async def translate_chapter_async(
    chapter_file: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
    use_flex_service_tier: bool = True,
    max_retries: int = 3,
) -> tuple[str, str]:
    chapter_path = Path(chapter_file)
    sheet_path = (
        Path(character_sheet_file)
        if character_sheet_file
        else _default_sheet_path(chapter_path, target_language)
    )
    translated_path, updated_sheet_path = _output_paths(chapter_path, sheet_path)

    if translated_path.exists():
        print(f"Skipping already translated chapter: {translated_path}")
        translated = translated_path.read_text(encoding="utf-8")
        sheet_source = updated_sheet_path if updated_sheet_path.exists() else sheet_path
        sheet = (
            sheet_source.read_text(encoding="utf-8") if sheet_source.exists() else ""
        )
        return translated, sheet

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    chapter_text = chapter_path.read_text(encoding="utf-8")
    legacy_sheet_path = _legacy_default_sheet_path(chapter_path, target_language)
    if sheet_path.exists():
        character_sheet = sheet_path.read_text(encoding="utf-8")
    elif not character_sheet_file and legacy_sheet_path.exists():
        character_sheet = legacy_sheet_path.read_text(encoding="utf-8")
    else:
        character_sheet = ""
    chapter_title, chapter_body = _split_title(chapter_text, chapter_path)

    response_text = None
    last_error: Exception | None = None
    async with OpenRouter(api_key=api_key) as open_router:
        try:
            character_sheet = await _compact_character_sheet_async(
                open_router, target_language, character_sheet, use_flex_service_tier
            )
            if character_sheet.strip():
                updated_sheet_path.parent.mkdir(parents=True, exist_ok=True)
                updated_sheet_path.write_text(character_sheet, encoding="utf-8")
        except Exception as exc:
            print(f"Character sheet compaction failed; using existing sheet: {exc}")

        for attempt in range(1, max_retries + 1):
            try:
                response = await open_router.chat.send_async(
                    messages=_build_messages(
                        chapter_path,
                        target_language,
                        character_sheet,
                        chapter_title,
                        chapter_body,
                    ),
                    model=MODEL,
                    provider={"sort": "price"},
                    service_tier="flex" if use_flex_service_tier else None,
                    temperature=0.2,
                )
                print(f"usage: {response.usage}")
                response_text = _extract_response_text(response)
                translated_chapter, updated_character_sheet = _parse_translation_response(
                    response_text
                )
                break
            except Exception as exc:
                last_error = exc
                print(
                    f"Translation attempt {attempt}/{max_retries} failed for {chapter_path.name}: {exc}"
                )
        else:
            error = last_error or RuntimeError("translation failed")
            failed_path = _save_failed_translation(chapter_path, error, response_text)
            raise RuntimeError(f"Saved failed translation to {failed_path}") from error

    translated_chapter = _preserve_original_title(translated_chapter, chapter_title)
    updated_character_sheet = updated_character_sheet.strip() + "\n"

    translated_path.parent.mkdir(parents=True, exist_ok=True)
    updated_sheet_path.parent.mkdir(parents=True, exist_ok=True)
    translated_path.write_text(translated_chapter, encoding="utf-8")
    updated_sheet_path.write_text(updated_character_sheet, encoding="utf-8")
    print(f"Saved translated chapter to {translated_path}")
    print(f"Saved character sheet to {updated_sheet_path}")

    return translated_chapter, updated_character_sheet


def translate_chapter(
    chapter_file: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
    use_flex_service_tier: bool = True,
    max_retries: int = 3,
) -> tuple[str, str]:
    return asyncio.run(
        translate_chapter_async(
            chapter_file,
            target_language,
            character_sheet_file,
            use_flex_service_tier,
            max_retries,
        )
    )


def main(
    chapter_file: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
    use_flex_service_tier: bool = True,
    max_retries: int = 3,
) -> tuple[str, str]:
    return translate_chapter(
        chapter_file,
        target_language,
        character_sheet_file,
        use_flex_service_tier,
        max_retries,
    )


async def translate_chapters_async(
    chapter_dir: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
    start: int | None = None,
    end: int | None = None,
    use_flex_service_tier: bool = True,
    max_retries: int = 3,
) -> None:
    chapter_files = _chapter_slice(
        sorted(Path(chapter_dir).glob("*.txt"), key=_natural_sort_key), start, end
    )
    for chapter_file in chapter_files:
        try:
            _, updated_sheet = await translate_chapter_async(
                chapter_file,
                target_language,
                character_sheet_file,
                use_flex_service_tier,
                max_retries,
            )
        except Exception as exc:
            print(f"Skipping failed chapter {chapter_file.name}: {exc}")
            continue
        character_sheet_file = (
            Path(character_sheet_file)
            if character_sheet_file
            else _default_sheet_path(chapter_file, target_language)
        )
        Path(character_sheet_file).write_text(updated_sheet, encoding="utf-8")


def translate_chapters(
    chapter_dir: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
    start: int | None = None,
    end: int | None = None,
    use_flex_service_tier: bool = True,
    max_retries: int = 3,
) -> None:
    asyncio.run(
        translate_chapters_async(
            chapter_dir,
            target_language,
            character_sheet_file,
            start=start,
            end=end,
            use_flex_service_tier=use_flex_service_tier,
            max_retries=max_retries,
        )
    )
