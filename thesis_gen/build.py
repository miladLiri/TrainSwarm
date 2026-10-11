# -*- coding: utf-8 -*-
"""Thesis builder: Combines all chapters into Thesis.md and prints statistics."""

import os
import re
import sys
from pathlib import Path

# Ensure thesis_gen directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ch1_intro import get_front_matter_and_ch1
from ch2_theory import get_ch2
from ch3_arch import get_ch3
from ch4_impl import get_ch4
from ch5_eval import get_ch5
from ch6_conclusion import get_ch6
from references import get_references

def build_thesis(output_path="Thesis.md"):
    parts = [
        get_front_matter_and_ch1(),
        get_ch2(),
        get_ch3(),
        get_ch4(),
        get_ch5(),
        get_ch6(),
        get_references(),
    ]

    full_text = "\n\n---\n\n".join(parts)

    out_file = Path(output_path).resolve()
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(full_text)

    char_count = len(full_text)
    # Persian/English word count
    words = re.findall(r'\S+', full_text)
    word_count = len(words)
    lines_count = len(full_text.splitlines())

    # In Microsoft Word, a typical Persian academic page (font B Nazanin 13 or 14, line spacing 1.5, standard margins)
    # contains around 280-320 words per page (or including tables, diagrams, equations, around 250-280 words/page).
    est_pages_min = word_count / 320
    est_pages_max = word_count / 260

    print("=" * 60)
    print(f"Thesis successfully built: {out_file}")
    print(f"File size: {out_file.stat().st_size:,} bytes")
    print(f"Total lines: {lines_count:,}")
    print(f"Total characters: {char_count:,}")
    print(f"Total word count: {word_count:,}")
    print(f"Estimated Word Document Pages: {est_pages_min:.1f} to {est_pages_max:.1f} pages")
    print("=" * 60)

    return full_text

if __name__ == "__main__":
    build_thesis()
