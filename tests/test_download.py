import json

import download


def test_sanitize_segment_empty():
    assert download.sanitize_segment("") == ""
    assert download.sanitize_segment(None) == ""


def test_sanitize_segment_normalizes():
    assert download.sanitize_segment("Foo Bar!! ") == "Foo-Bar"
    assert download.sanitize_segment("a   b") == "a-b"
    assert download.sanitize_segment("--x--y--") == "x-y"


def test_truncate_title_empty():
    assert download.truncate_title("") == "Untitled"
    assert download.truncate_title("!!! @@@") == "Untitled"


def test_truncate_title_word_boundary():
    title = "alpha beta gamma delta epsilon zeta eta theta"
    result = download.truncate_title(title, max_len=20)
    assert len(result) <= 20
    assert not result.endswith("-")
    assert result.startswith("alpha")


def test_build_filename_basic():
    paper = {
        "first_author_surname": "smith",
        "year": 2020,
        "title": "Deep Nets",
        "source": "arxiv",
        "source_id": "1234.5678",
    }
    assert download.build_filename(paper) == "Smith_2020_Deep-Nets_arxiv-1234.5678.pdf"


def test_build_filename_missing_year_and_author():
    paper = {
        "first_author_surname": "unknown",
        "title": "Study",
        "source": "core",
    }
    assert download.build_filename(paper) == "Unknown_nd_Study.pdf"


def test_build_filename_doi_when_no_source_id():
    paper = {
        "first_author_surname": "Roe",
        "year": 2019,
        "title": "Work",
        "source": "dblp",
        "doi": "10.1000/xyz",
    }
    assert download.build_filename(paper) == "Roe_2019_Work_10.1000-xyz.pdf"


def test_dedup_key_variants():
    assert (
        download.dedup_key({"source": "arxiv", "source_id": "1"}, "f.pdf") == "arxiv:1"
    )
    assert download.dedup_key({"doi": "10.1/x"}, "f.pdf") == "doi:10.1/x"
    assert download.dedup_key({}, "f.pdf") == "file:f.pdf"


def test_upsert_index_overwrite_and_append():
    index = [{"_key": "a", "title": "old"}]
    download.upsert_index(index, {"_key": "a", "title": "new"}, "a")
    assert len(index) == 1
    assert index[0]["title"] == "new"
    download.upsert_index(index, {"_key": "b", "title": "other"}, "b")
    assert len(index) == 2


def test_load_index_missing(tmp_path):
    assert download.load_index(tmp_path / "nope.json") == []


def test_load_index_corrupt(tmp_path):
    path = tmp_path / "index.json"
    path.write_text("{ not valid json", encoding="utf-8")
    assert download.load_index(path) == []


def test_build_entry_shape():
    paper = {
        "title": "T",
        "authors": ["Jane Roe"],
        "year": 2021,
        "source": "arxiv",
        "source_id": "1.2",
        "doi": None,
        "pdf_url": "http://p",
    }
    entry = download.build_entry(paper, "f.pdf")
    assert entry["filename"] == "f.pdf"
    assert entry["_key"] == "arxiv:1.2"
    assert entry["authors"] == ["Jane Roe"]
    assert "downloaded_at" in entry
    json.dumps(entry)
