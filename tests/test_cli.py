import json
from pathlib import Path

from click.testing import CliRunner

from docmd.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_convert_writes_output_file(tmp_path):
    out_file = tmp_path / "out.md"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", str(FIXTURES / "sample.pdf"), "-o", str(out_file)])

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    content = out_file.read_text()
    assert "Q3 Regional Sales Report" in content


def test_cli_convert_prints_to_stdout_by_default():
    runner = CliRunner()
    result = runner.invoke(main, ["convert", str(FIXTURES / "sample.pdf")])

    assert result.exit_code == 0, result.output
    assert "Q3 Regional Sales Report" in result.output


def test_cli_convert_missing_file_errors_cleanly():
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "/no/such/file.pdf"])
    assert result.exit_code != 0


def test_cli_convert_format_rag_writes_chunk_json(tmp_path):
    out_file = tmp_path / "out.json"
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", str(FIXTURES / "sample.pdf"), "--format", "rag", "-o", str(out_file)]
    )

    assert result.exit_code == 0, result.output
    chunks = json.loads(out_file.read_text())
    assert isinstance(chunks, list)
    assert any(c["text"] == "Q3 Regional Sales Report" for c in chunks)
    assert all({"text", "page", "section", "content_type", "bbox"} <= c.keys() for c in chunks)


def test_cli_chunk_max_tokens_merges_chunks(tmp_path):
    out_file = tmp_path / "out.json"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "convert",
            str(FIXTURES / "running_header.pdf"),
            "--format",
            "rag",
            "--chunk-max-tokens",
            "1000",
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0, result.output
    chunks = json.loads(out_file.read_text())
    # Unmerged, this fixture produces 9 chunks (see test_chunks.py); merged
    # up to 1000 tokens, each section's heading absorbs its own paragraph.
    assert len(chunks) < 9


def test_cli_extract_tables_writes_one_csv_per_table(tmp_path):
    out_dir = tmp_path / "tables"
    runner = CliRunner()
    result = runner.invoke(
        main, ["extract", str(FIXTURES / "stress.pdf"), "--tables", "csv", "-o", str(out_dir)]
    )

    assert result.exit_code == 0, result.output
    csv_files = sorted(out_dir.glob("*.csv"))
    assert len(csv_files) >= 1
    assert csv_files[0].read_text().splitlines()[0]  # a real header row, not empty


def test_cli_extract_no_tables_does_not_error(tmp_path):
    out_dir = tmp_path / "tables"
    runner = CliRunner()
    result = runner.invoke(
        main, ["extract", str(FIXTURES / "with_image.pdf"), "--tables", "csv", "-o", str(out_dir)]
    )
    assert result.exit_code == 0, result.output
