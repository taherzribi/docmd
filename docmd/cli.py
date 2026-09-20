"""`docmd convert <file> [-o output.md]`"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import click

from docmd import convert_document
from docmd.config import ConvertConfig
from docmd.errors import DocmdError
from docmd.tables import extract_tables_as_csv


@click.group()
@click.version_option(package_name="docmd")
def main() -> None:
    """docmd: convert PDF/DOCX/PPTX to clean, structure-preserving Markdown."""


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write Markdown to this file instead of stdout.",
)
@click.option(
    "--force-ocr",
    is_flag=True,
    default=False,
    help="Force OCR even on pages that already have a text layer.",
)
@click.option(
    "--use-llm",
    is_flag=True,
    default=False,
    help=(
        "Use an LLM pass for higher-fidelity table/form extraction "
        "(needs a provider API key set for Marker; has a real marginal cost)."
    ),
)
@click.option(
    "--image-mode",
    type=click.Choice(["placeholder", "alt-text", "skip"]),
    default="placeholder",
    show_default=True,
    help="How to represent images in the output.",
)
@click.option(
    "--image-dir",
    "image_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to save image files in --image-mode alt-text. Defaults to "
    "the output file's directory when -o is given; without -o, images "
    "won't be saved unless this is set explicitly.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "rag"]),
    default="markdown",
    show_default=True,
    help=(
        "'rag' writes a JSON array of chunks (text/page/section/content_type/bbox) "
        "instead of Markdown - see ConvertConfig.include_chunks."
    ),
)
@click.option(
    "--chunk-max-tokens",
    "chunk_max_tokens",
    type=int,
    default=None,
    help=(
        "With --format rag, merge adjacent text/heading chunks up to roughly "
        "this many tokens instead of one chunk per raw block - see "
        "ConvertConfig.chunk_max_tokens. Ignored with --format markdown."
    ),
)
def convert(
    file: Path,
    output: Path | None,
    force_ocr: bool,
    use_llm: bool,
    image_mode: str,
    image_dir: Path | None,
    output_format: str,
    chunk_max_tokens: int | None,
) -> None:
    """Convert FILE to Markdown."""
    config = ConvertConfig(
        force_ocr=force_ocr,
        use_llm=use_llm,
        image_mode=image_mode,
        include_chunks=(output_format == "rag"),
        chunk_max_tokens=chunk_max_tokens,
    )

    if image_mode == "alt-text" and image_dir is None:
        if output is not None:
            image_dir = output.parent
        else:
            click.echo(
                "warning: --image-mode alt-text with no -o/--image-dir - "
                "image links in the output won't resolve to real files. "
                "Pass --image-dir to save images somewhere.",
                err=True,
            )

    try:
        result = convert_document(str(file), config=config, output_dir=image_dir)
    except DocmdError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    if output_format == "rag":
        assert result.chunks is not None  # guaranteed by include_chunks=True above
        content = json.dumps([dataclasses.asdict(chunk) for chunk in result.chunks], indent=2)
    else:
        content = result.markdown

    if output is not None:
        output.write_text(content, encoding="utf-8")
        click.echo(f"wrote {output} ({result.page_count} page(s))", err=True)
    else:
        click.echo(content)


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--tables",
    "extract_tables",
    type=click.Choice(["csv"]),
    required=True,
    help="What to extract - currently only 'csv' (one file per table found).",
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
    help="Directory to write extracted files into (created if it doesn't exist).",
)
def extract(file: Path, extract_tables: str, output_dir: Path) -> None:
    """Extract structured data (tables) from FILE, independent of the
    Markdown output - each table becomes its own file."""
    try:
        result = convert_document(str(file))
    except DocmdError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    tables = extract_tables_as_csv(result.markdown)
    if not tables:
        click.echo("no tables found", err=True)
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    for index, csv_content in enumerate(tables, start=1):
        (output_dir / f"table_{index}.csv").write_text(csv_content, encoding="utf-8")
    click.echo(f"wrote {len(tables)} table(s) to {output_dir}", err=True)


if __name__ == "__main__":
    main()
