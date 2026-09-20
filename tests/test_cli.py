import json
import shutil
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


def test_cli_validate_clean_document_exits_zero():
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(FIXTURES / "stress.pdf")])
    assert result.exit_code == 0, result.output
    assert "heading" in result.output
    assert "table" in result.output


def test_cli_batch_converts_every_file_and_mirrors_structure(tmp_path):
    input_dir = tmp_path / "input"
    subdir = input_dir / "sub"
    subdir.mkdir(parents=True)
    shutil.copy(FIXTURES / "sample.pdf", input_dir / "sample.pdf")
    shutil.copy(FIXTURES / "stress.pdf", subdir / "stress.pdf")
    out_dir = tmp_path / "output"

    runner = CliRunner()
    result = runner.invoke(main, ["batch", str(input_dir), "-o", str(out_dir)])

    assert result.exit_code == 0, result.output
    assert (out_dir / "sample.md").exists()
    assert (out_dir / "sub" / "stress.md").exists()
    assert "Q3 Regional Sales Report" in (out_dir / "sample.md").read_text()
    assert "2 succeeded, 0 failed, 0 skipped" in result.output


def test_cli_batch_skips_already_converted_files_on_rerun(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy(FIXTURES / "sample.pdf", input_dir / "sample.pdf")
    out_dir = tmp_path / "output"

    runner = CliRunner()
    runner.invoke(main, ["batch", str(input_dir), "-o", str(out_dir)])
    result = runner.invoke(main, ["batch", str(input_dir), "-o", str(out_dir)])

    assert result.exit_code == 0, result.output
    assert "0 succeeded, 0 failed, 1 skipped" in result.output


def test_cli_batch_overwrite_reconverts_existing_files(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy(FIXTURES / "sample.pdf", input_dir / "sample.pdf")
    out_dir = tmp_path / "output"

    runner = CliRunner()
    runner.invoke(main, ["batch", str(input_dir), "-o", str(out_dir)])
    result = runner.invoke(main, ["batch", str(input_dir), "-o", str(out_dir), "--overwrite"])

    assert result.exit_code == 0, result.output
    assert "1 succeeded, 0 failed, 0 skipped" in result.output


def test_cli_batch_one_bad_file_does_not_block_the_others(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy(FIXTURES / "sample.pdf", input_dir / "sample.pdf")
    (input_dir / "broken.pdf").write_text("not a real pdf")
    out_dir = tmp_path / "output"

    runner = CliRunner()
    result = runner.invoke(main, ["batch", str(input_dir), "-o", str(out_dir)])

    assert result.exit_code != 0  # non-zero because one file failed
    assert (out_dir / "sample.md").exists()  # the good file still converted
    assert "1 succeeded, 1 failed, 0 skipped" in result.output


def test_cli_batch_empty_directory_does_not_error(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    out_dir = tmp_path / "output"

    runner = CliRunner()
    result = runner.invoke(main, ["batch", str(input_dir), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output


def test_cli_search_finds_result_from_batch_rag_output(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy(FIXTURES / "sample.pdf", input_dir / "sample.pdf")
    chunks_dir = tmp_path / "chunks"

    runner = CliRunner()
    batch_result = runner.invoke(main, ["batch", str(input_dir), "-o", str(chunks_dir), "--format", "rag"])
    assert batch_result.exit_code == 0, batch_result.output

    search_result = runner.invoke(main, ["search", str(chunks_dir), "regional sales"])
    assert search_result.exit_code == 0, search_result.output
    assert "sample.json" in search_result.output
    assert "Page 0" in search_result.output


def test_cli_search_no_results_does_not_error(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["search", str(empty_dir), "nothing here"])
    assert result.exit_code == 0, result.output
    assert "no results" in result.output
