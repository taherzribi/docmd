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
