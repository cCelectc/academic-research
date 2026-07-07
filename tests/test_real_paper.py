import os

import pytest
import requests
from conftest import run_parser

ARXIV_PDF = "https://arxiv.org/pdf/1706.03762"
ABSTRACT_SENTENCE = (
    "The dominant sequence transduction models are based on complex "
    "recurrent or convolutional neural networks"
)


@pytest.mark.skipif(
    os.environ.get("PARSE_PDF_REAL") != "1",
    reason="opt-in network test; set PARSE_PDF_REAL=1 to run",
)
def test_real_arxiv_reading_order(tmp_path):
    pdf = tmp_path / "attention.pdf"
    try:
        resp = requests.get(ARXIV_PDF, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        pytest.skip(f"network unavailable: {e}")
    pdf.write_bytes(resp.content)

    proc = run_parser(pdf)
    assert proc.returncode == 0, proc.stderr
    import json

    data = json.loads(proc.stdout)

    assert len(data["full_text"]) > 5000
    normalized = " ".join(data["full_text"].split())
    assert ABSTRACT_SENTENCE in normalized, (
        "abstract sentence not contiguous — column interleaving suspected"
    )
    titles = " ".join(s["title"].lower() for s in data["sections"])
    assert any(k in titles for k in ("introduction", "conclusion", "references"))
