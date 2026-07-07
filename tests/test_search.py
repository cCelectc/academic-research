import search


class FakeResp:
    def __init__(self, content=b"", json_data=None):
        self.content = content
        self._json = json_data

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


def _patch_get(monkeypatch, resp):
    monkeypatch.setattr(search.requests, "get", lambda *a, **k: resp)


ARXIV_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <title>Attention Is All You Need</title>
    <summary>We propose a new architecture.</summary>
    <id>http://arxiv.org/abs/1234.5678v1</id>
    <published>2021-01-01T00:00:00Z</published>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <link href="https://doi.org/10.1000/abc"/>
  </entry>
</feed>
"""

EXPECTED_KEYS = {
    "source",
    "title",
    "authors",
    "year",
    "abstract",
    "pdf_url",
    "doi",
    "source_id",
    "first_author_surname",
    "citation_count",
}


def test_search_arxiv_parses(monkeypatch):
    _patch_get(monkeypatch, FakeResp(content=ARXIV_XML))
    results = search.search_arxiv("q", 5)
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == EXPECTED_KEYS
    assert r["source"] == "arxiv"
    assert r["source_id"] == "1234.5678v1"
    assert r["pdf_url"] == "https://arxiv.org/pdf/1234.5678v1"
    assert r["year"] == 2021
    assert r["doi"] == "10.1000/abc"
    assert r["first_author_surname"] == "Vaswani"
    assert r["citation_count"] is None


def test_search_semantic_scholar_parses(monkeypatch):
    _patch_get(
        monkeypatch,
        FakeResp(
            json_data={
                "data": [
                    {
                        "title": "T",
                        "authors": [{"name": "Jane Roe"}],
                        "year": 2019,
                        "abstract": "A",
                        "externalIds": {"DOI": "10.x/y"},
                        "openAccessPdf": {"url": "http://p"},
                        "citationCount": 42,
                        "paperId": "pid",
                    }
                ]
            }
        ),
    )
    results = search.search_semantic_scholar("q", 5)
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == EXPECTED_KEYS
    assert r["source"] == "semantic_scholar"
    assert r["pdf_url"] == "http://p"
    assert r["doi"] == "10.x/y"
    assert r["citation_count"] == 42
    assert r["source_id"] == "pid"
    assert r["first_author_surname"] == "Roe"


def test_search_semantic_scholar_no_pdf(monkeypatch):
    _patch_get(
        monkeypatch,
        FakeResp(
            json_data={
                "data": [
                    {
                        "title": "T",
                        "authors": [],
                        "openAccessPdf": None,
                    }
                ]
            }
        ),
    )
    results = search.search_semantic_scholar("q", 5)
    assert results[0]["pdf_url"] is None


def test_search_dblp_parses(monkeypatch):
    _patch_get(
        monkeypatch,
        FakeResp(
            json_data={
                "result": {
                    "hits": {
                        "hit": [
                            {
                                "info": {
                                    "title": "T",
                                    "year": "2018",
                                    "authors": {"author": {"text": "John Doe"}},
                                    "doi": "10.a/b",
                                    "key": "conf/x",
                                }
                            }
                        ]
                    }
                }
            }
        ),
    )
    results = search.search_dblp("q", 5)
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == EXPECTED_KEYS
    assert r["source"] == "dblp"
    assert r["authors"] == ["John Doe"]
    assert r["year"] == 2018
    assert r["abstract"] is None
    assert r["pdf_url"] is None
    assert r["source_id"] == "conf/x"
    assert r["first_author_surname"] == "Doe"


def test_search_core_parses(monkeypatch):
    _patch_get(
        monkeypatch,
        FakeResp(
            json_data={
                "results": [
                    {
                        "title": "T",
                        "authors": [{"name": "Amy Lee"}],
                        "yearPublished": 2022,
                        "abstract": "A",
                        "downloadUrl": "http://d",
                        "doi": "10.c/d",
                        "id": 99,
                    }
                ]
            }
        ),
    )
    results = search.search_core("q", 5)
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == EXPECTED_KEYS
    assert r["source"] == "core"
    assert r["pdf_url"] == "http://d"
    assert r["source_id"] == "99"
    assert r["citation_count"] is None
    assert r["first_author_surname"] == "Lee"
