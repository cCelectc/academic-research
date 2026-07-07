from conftest import (
    make_full_width_header,
    make_no_text,
    make_repeated_figs,
    make_single_column,
    make_two_column,
    make_two_paragraphs,
    make_typographic_sections,
    make_uniform_sections,
    make_year_trap,
    run_parser,
)


def test_two_column_reading_order(tmp_path, parse):
    pdf = tmp_path / "two_col.pdf"
    make_two_column(pdf)
    data, _ = parse(pdf)
    ft = data["full_text"]
    assert ft.index("LMARK") < ft.index("RMARK")
    assert ft.rindex("LMARK") < ft.index("RMARK")


def test_full_width_not_dropped(tmp_path, parse):
    pdf = tmp_path / "full_width.pdf"
    make_full_width_header(pdf)
    data, _ = parse(pdf)
    assert "FULLWIDTH BANNER HEADING" in data["full_text"]


def test_single_column_word_order(tmp_path, parse):
    pdf = tmp_path / "single_col.pdf"
    make_single_column(pdf)
    data, _ = parse(pdf)
    assert "the quick brown fox jumps" in data["full_text"]


def test_paragraph_chunking(tmp_path, parse):
    pdf = tmp_path / "paras.pdf"
    make_two_paragraphs(pdf)
    data, _ = parse(pdf)
    page1 = data["text_per_page"]["1"]
    assert len(page1.split("\n\n")) == 2
    assert "\n" in page1.split("\n\n")[0]


def test_typographic_section(tmp_path, parse):
    pdf = tmp_path / "typo.pdf"
    make_typographic_sections(pdf)
    data, _ = parse(pdf)
    matches = [s for s in data["sections"] if "Zephyr Mechanism" in s["title"]]
    assert matches, data["sections"]
    assert matches[0]["method"] == "typographic"


def test_uniform_fallback(tmp_path, parse):
    pdf = tmp_path / "uniform.pdf"
    make_uniform_sections(pdf)
    data, _ = parse(pdf)
    matches = [s for s in data["sections"] if s["title"].startswith("3. Method")]
    assert matches, data["sections"]
    assert matches[0]["method"] == "fallback"


def test_figures_deduped(tmp_path, parse):
    pdf = tmp_path / "figs.pdf"
    make_repeated_figs(pdf)
    data, _ = parse(pdf)
    numbers = [f["number"] for f in data["figures"]]
    assert numbers == [3]


def test_year_not_stray(tmp_path, parse):
    pdf = tmp_path / "year.pdf"
    make_year_trap(pdf)
    data, _ = parse(pdf)
    assert data["metadata"].get("year") != 2019


def test_corrupt_pdf_errors(tmp_path):
    pdf = tmp_path / "corrupt.pdf"
    pdf.write_bytes(b"%PDF-1.4 garbage not a real pdf")
    proc = run_parser(pdf)
    assert proc.returncode != 0
    assert "Error" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_no_text_layer_warns(tmp_path):
    pdf = tmp_path / "no_text.pdf"
    make_no_text(pdf)
    proc = run_parser(pdf)
    assert proc.returncode == 0
    assert "no text layer" in proc.stderr


def test_bad_page_range(tmp_path):
    pdf = tmp_path / "single_col.pdf"
    make_single_column(pdf)
    proc = run_parser(pdf, "--pages", "abc")
    assert proc.returncode != 0
    assert "invalid page range" in proc.stderr
