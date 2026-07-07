import json
import subprocess
import sys
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "academic-research"
    / "scripts"
    / "parse_pdf.py"
)


def run_parser(pdf_path, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--pdf", str(pdf_path), *args],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def parse():
    def _parse(pdf_path, *args):
        proc = run_parser(pdf_path, *args)
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"parser did not emit JSON (rc={proc.returncode})\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            ) from e
        return data, proc

    return _parse


def _lines(c, x, y, texts, leading=14, font="Helvetica", size=10):
    c.setFont(font, size)
    for i, t in enumerate(texts):
        c.drawString(x, y - i * leading, t)


def make_two_column(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(c, 72, 700, [f"LMARK left column line {i}" for i in range(5)])
    _lines(c, 330, 700, [f"RMARK right column line {i}" for i in range(5)])
    c.save()


def make_single_column(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(c, 72, 700, ["the quick brown fox jumps"])
    c.save()


def make_full_width_header(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(
        72, 730, "FULLWIDTH BANNER HEADING SPANNING THE ENTIRE PAGE WIDTH HERE"
    )
    _lines(c, 72, 700, [f"LMARK left column line {i}" for i in range(5)])
    _lines(c, 330, 700, [f"RMARK right column line {i}" for i in range(5)])
    c.save()


def make_two_paragraphs(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(c, 72, 700, ["first paragraph line one", "first paragraph line two"])
    _lines(c, 72, 620, ["second paragraph line one", "second paragraph line two"])
    c.save()


def make_typographic_sections(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(c, 72, 720, ["Some introductory body text before the section."])
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 680, "Zephyr Mechanism")
    _lines(c, 72, 650, ["Body text describing the zephyr mechanism in detail."])
    c.save()


def make_uniform_sections(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(
        c,
        72,
        720,
        [
            "Preliminary discussion of the setup and notation.",
            "3. Method",
            "We describe the proposed method in this section.",
        ],
        leading=30,
    )
    c.save()


def make_repeated_figs(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(
        c,
        72,
        700,
        [
            "As shown in Fig. 3 the results improve.",
            "We revisit Fig. 3 with more data.",
            "Finally see Figure 3 again for the summary.",
        ],
        leading=20,
    )
    c.save()


def make_year_trap(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(
        c,
        72,
        700,
        [
            "This paper builds on prior work.",
            "[1] Smith et al. 2019. Some cited paper title.",
        ],
        leading=20,
    )
    c.save()


def make_no_text(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.rect(100, 400, 300, 200, fill=1, stroke=0)
    c.save()
