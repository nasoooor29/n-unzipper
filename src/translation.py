import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from openrouter import OpenRouter


MODEL = "google/gemini-2.5-flash-lite"


def _book_root_for(chapter_file: Path) -> Path:
    if chapter_file.parent.name.lower() == "txt":
        return chapter_file.parent.parent
    return chapter_file.parent


def _default_sheet_path(chapter_file: Path) -> Path:
    return _book_root_for(chapter_file) / "characterSheet" / "character_sheet.txt"


def _output_paths(chapter_file: Path, character_sheet_file: Path | None) -> tuple[Path, Path]:
    book_root = _book_root_for(chapter_file)
    sheet_name = character_sheet_file.name if character_sheet_file else "character_sheet.txt"
    return (
        book_root / "translated" / chapter_file.name,
        book_root / "characterSheet" / sheet_name,
    )


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


def _parse_translation_response(content: str) -> tuple[str, str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenRouter response was not valid JSON.") from exc

    translated_chapter = str(data.get("translated_chapter", "")).strip()
    updated_character_sheet = str(data.get("updated_character_sheet", "")).strip()
    if not translated_chapter or not updated_character_sheet:
        raise ValueError(
            "OpenRouter response must include translated_chapter and updated_character_sheet."
        )
    return translated_chapter, updated_character_sheet


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
        else "The character/reference sheet is empty. Create a compact sheet containing "
        "the most important recurring characters, groups, locations, relationships, "
        "power levels, countries, factions, titles, and story-specific terms from this chapter."
    )

    system_prompt = f"""
You are a literary translator for novels and story chapters.
Translate the chapter into {target_language} while preserving story continuity.

Rules:
- Preserve the first line/chapter title exactly as provided. Do not translate, rewrite, or reformat it.
- Preserve names, relationships, titles, locations, power systems, ranks, countries, factions, and story-specific terminology consistently.
- Use the character/reference sheet to keep characters, relationships, titles, locations, terminology, power levels, and country/faction relations consistent.
- Keep prose natural in {target_language}, but do not summarize or omit content.
- Return valid JSON only. Do not wrap it in Markdown.
- The JSON must contain exactly these string fields: translated_chapter, updated_character_sheet.
- translated_chapter is message 1 and must contain the full translated chapter, starting with the unchanged original title.
- updated_character_sheet is message 2 and must contain the updated reference sheet.
- Keep the reference sheet easy to skim. Use clear bullet hierarchy. Use no more than 4 top-level sheets/categories when possible, and keep entries concise.
- Organize people and concepts under their relevant kingdom, village, faction, family, power system, location, or category.
""".strip()

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


async def translate_chapter_async(
    chapter_file: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
) -> tuple[str, str]:
    chapter_path = Path(chapter_file)
    sheet_path = Path(character_sheet_file) if character_sheet_file else _default_sheet_path(chapter_path)
    translated_path, updated_sheet_path = _output_paths(chapter_path, sheet_path)

    if translated_path.exists():
        print(f"Skipping already translated chapter: {translated_path}")
        translated = translated_path.read_text(encoding="utf-8")
        sheet_source = updated_sheet_path if updated_sheet_path.exists() else sheet_path
        sheet = sheet_source.read_text(encoding="utf-8") if sheet_source.exists() else ""
        return translated, sheet

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    chapter_text = chapter_path.read_text(encoding="utf-8")
    character_sheet = sheet_path.read_text(encoding="utf-8") if sheet_path.exists() else ""
    chapter_title, chapter_body = _split_title(chapter_text, chapter_path)

    async with OpenRouter(api_key=api_key) as open_router:
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
            response_format={"type": "json_object"},
            temperature=0.2,
        )

    translated_chapter, updated_character_sheet = _parse_translation_response(
        _extract_response_text(response)
    )
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
) -> tuple[str, str]:
    return asyncio.run(
        translate_chapter_async(chapter_file, target_language, character_sheet_file)
    )


def main(
    chapter_file: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
) -> tuple[str, str]:
    return translate_chapter(chapter_file, target_language, character_sheet_file)


async def translate_chapters_async(
    chapter_dir: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
    start: int | None = None,
    end: int | None = None,
) -> None:
    chapter_files = _chapter_slice(
        sorted(Path(chapter_dir).glob("*.txt"), key=_natural_sort_key), start, end
    )
    for chapter_file in chapter_files:
        _, updated_sheet = await translate_chapter_async(
            chapter_file, target_language, character_sheet_file
        )
        character_sheet_file = _output_paths(
            chapter_file,
            Path(character_sheet_file) if character_sheet_file else None,
        )[1]
        Path(character_sheet_file).write_text(updated_sheet, encoding="utf-8")


def translate_chapters(
    chapter_dir: str | Path,
    target_language: str,
    character_sheet_file: str | Path | None = None,
    start: int | None = None,
    end: int | None = None,
) -> None:
    asyncio.run(
        translate_chapters_async(
            chapter_dir,
            target_language,
            character_sheet_file,
            start=start,
            end=end,
        )
    )
