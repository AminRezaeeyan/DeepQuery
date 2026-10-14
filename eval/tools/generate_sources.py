"""
Builds the non-paper source files in eval/sources/ deterministically.

The papers (*.pdf) are real; everything this script writes describes a
fictional lab reproducing them, so answers can only come from these files.
Run from the repository root:

    .venv/bin/python eval/tools/generate_sources.py
"""
import csv
import json
import random
from pathlib import Path

import pandas as pd
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

SOURCES = Path(__file__).resolve().parents[1] / "sources"


# --------------------------------------------------------------------------
# reproduction_runs.xlsx
# --------------------------------------------------------------------------

SYSTEMS = {
    # system: (base F1 per dataset, gpu, gpu hours per run)
    "BLINK-bi": ({"AIDA": 79.2, "MSNBC": 84.1, "WNED-WIKI": 70.3}, "V100", 3.5),
    "BLINK-cross": ({"AIDA": 86.4, "MSNBC": 88.7, "WNED-WIKI": 75.9}, "V100", 11.0),
    "ReFinED": ({"AIDA": 92.8, "MSNBC": 93.6, "WNED-WIKI": 86.2}, "T4", 1.25),
    "CLINK-cross": ({"AIDA": 87.1, "MSNBC": 89.9, "WNED-WIKI": 76.8}, "A100", 6.5),
}
GPU_PRICES = {"V100": 2.48, "T4": 0.53, "A100": 3.67}


def build_runs():
    rng = random.Random(7)
    rows = []
    run_id = 1
    for system, (base, gpu, hours) in SYSTEMS.items():
        for dataset, f1 in base.items():
            for seed in (1, 2, 3):
                rows.append({
                    "run_id": f"R{run_id:03d}",
                    "system": system,
                    "dataset": dataset,
                    "seed": seed,
                    "micro_f1": round(f1 + rng.uniform(-0.9, 0.9), 2),
                    "gpu": gpu,
                    "gpu_hours": round(hours * rng.uniform(0.9, 1.1), 2),
                    "status": "ok",
                })
                run_id += 1
    # Crashed attempts that were re-run: they must not count in any average.
    for system, dataset, f1 in [("ReFinED", "AIDA", 12.4), ("BLINK-cross", "MSNBC", 3.1),
                                ("CLINK-cross", "WNED-WIKI", 0.0), ("ReFinED", "WNED-WIKI", 41.7)]:
        gpu, hours = SYSTEMS[system][1], SYSTEMS[system][2]
        rows.append({
            "run_id": f"R{run_id:03d}", "system": system, "dataset": dataset, "seed": 4,
            "micro_f1": f1, "gpu": gpu, "gpu_hours": round(hours * 0.4, 2), "status": "failed",
        })
        run_id += 1
    return pd.DataFrame(rows)


def write_runs():
    runs = build_runs()
    prices = pd.DataFrame([{"gpu": g, "usd_per_hour": p} for g, p in GPU_PRICES.items()])
    notes = pd.DataFrame({"note": [
        "Reproduction study of entity linking systems, autumn 2026.",
        "Runs with status 'failed' crashed and were re-run; exclude them from every average.",
        "Failed runs were still billed: include them when computing cost.",
        "micro_f1 is InKB micro F1 on the named test set, in percent.",
    ]})
    with pd.ExcelWriter(SOURCES / "reproduction_runs.xlsx") as xl:
        runs.to_excel(xl, sheet_name="runs", index=False)
        prices.to_excel(xl, sheet_name="gpu_prices", index=False)
        notes.to_excel(xl, sheet_name="notes", index=False)
    return runs


# --------------------------------------------------------------------------
# nil_audit.csv
# --------------------------------------------------------------------------

EN_MENTIONS = ["Jaguar", "Mercury", "Apple", "The Birds", "Paris", "Amazon", "Phoenix", "Java", "Delta", "Orion"]
FA_MENTIONS = ["جگوار", "عطارد", "سیب", "پرندگان", "پاریس", "آمازون", "ققنوس", "جاوا"]


def write_audit():
    rng = random.Random(11)
    rows = []
    for i in range(1, 241):
        language = "fa" if rng.random() < 0.25 else "en"
        mention = rng.choice(FA_MENTIONS if language == "fa" else EN_MENTIONS)
        r = rng.random()
        if r < 0.55:
            gold, nil_type = f"Q{rng.randint(100, 9999)}", ""
        elif r < 0.75:
            gold, nil_type = "NIL", "missing_entity"
        else:
            gold, nil_type = "NIL", "non_entity_phrase"

        def predict(skill_entity, skill_nil):
            if gold == "NIL":
                return "NIL" if rng.random() < skill_nil else f"Q{rng.randint(100, 9999)}"
            return gold if rng.random() < skill_entity else rng.choice(["NIL", f"Q{rng.randint(100, 9999)}"])

        bi = predict(0.74, 0.86)
        cross = predict(0.86, 0.80 if nil_type == "non_entity_phrase" else 0.70)
        rows.append({
            "id": i, "language": language, "mention": mention, "gold": gold, "nil_type": nil_type,
            "bi_pred": bi, "cross_pred": cross, "cross_score": round(rng.uniform(0.05, 0.99), 3),
        })
    with open(SOURCES / "nil_audit.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Code files
# --------------------------------------------------------------------------

NIL_THRESHOLD_PY = '''"""NIL decision rule used in our reproduction (compare with Eq. 10 of the NIL paper)."""

EPSILON = 0.5

CANDIDATE_SCORES = {
    "Jaguar (car maker)": {"Jaguar Cars": 0.81, "Jaguar (animal)": 0.47},
    "the birds": {"The Birds (film)": 0.50, "The Birds (play)": 0.31},
    "Mercury": {"Mercury (planet)": 0.49, "Freddie Mercury": 0.49},
    "Apple": {"Apple Inc.": 0.92, "Apple (fruit)": 0.88},
    "phoenix": {"Phoenix, Arizona": 0.505, "Phoenix (mythology)": 0.495},
}


def link(scores, epsilon=EPSILON):
    best, score = max(scores.items(), key=lambda item: item[1])
    if score > epsilon:
        return best
    return "NIL"


if __name__ == "__main__":
    results = {mention: link(scores) for mention, scores in CANDIDATE_SCORES.items()}
    nil_count = sum(1 for entity in results.values() if entity == "NIL")
    for mention, entity in results.items():
        print(f"{mention} -> {entity}")
    print(f"NIL: {nil_count}/{len(results)}")
'''

RECALL_AT_K_PY = '''"""Recall@k for a retriever, from the rank of the gold entity per query."""

# 0-based rank of the gold entity in each query's candidate list; None = not retrieved.
GOLD_RANKS = [0, 3, None, 9, 10, 1, 63, 64, None, 0, 2, 15, 9, 31, 7, 100, 0, 5, 49, 12]


def recall_at_k(ranks, k):
    hits = sum(1 for r in ranks if r is not None and r <= k)
    return hits / len(ranks)


if __name__ == "__main__":
    for k in (1, 10, 64):
        print(f"R@{k} = {recall_at_k(GOLD_RANKS, k):.2f}")
'''

LATENCY_TS = '''// Estimates how long linking a corpus takes for a given system.

interface SystemProfile {
  name: string;
  msPerForwardPass: number;
  passesPerDocument: (mentions: number) => number;
}

const SYSTEMS: SystemProfile[] = [
  // ReFinED encodes all mentions of a 512-token chunk in one pass.
  { name: "refined", msPerForwardPass: 65, passesPerDocument: () => 1 },
  // A bi-encoder encodes each mention separately.
  { name: "bi-encoder", msPerForwardPass: 20, passesPerDocument: (m) => m },
  // A cross-encoder encodes each mention with each of its 30 candidates.
  { name: "cross-encoder", msPerForwardPass: 10, passesPerDocument: (m) => m * 30 },
];

export function corpusHours(system: SystemProfile, documents: number, mentionsPerDocument: number): number {
  const ms = documents * system.passesPerDocument(mentionsPerDocument) * system.msPerForwardPass;
  return ms / 1000 / 3600;
}

for (const system of SYSTEMS) {
  console.log(`${system.name}: ${corpusHours(system, 1_000_000, 25).toFixed(1)} h`);
}
'''


# --------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------

LAB_NOTES_MD = """# Entity linking reading group: notes

## 2026-09-18
- Read the ReFinED paper. Takeaway recorded by Sam: ReFinED is about 100x faster
  than the BLINK cross-encoder on AIDA-CoNLL, so we should drop BLINK entirely.
- Agreed to reproduce four systems: BLINK-bi, BLINK-cross, ReFinED and CLINK-cross
  (results in reproduction_runs.xlsx).

## 2026-09-25
- Nora audited 240 mentions for NIL behaviour (nil_audit.csv). About a quarter of
  them come from Persian news.
- Decision: our production NIL threshold is 0.4, lower than the NIL paper's 0.5,
  because missed links hurt us more than wrong NIL predictions.

## 2026-10-02
- Budget for the reproduction is capped at 400 USD of GPU time.
- Next meeting moved to 2026-10-16. Owner of the final report: Nora.
"""

YADDASHT_MD = """# یادداشت‌های جلسه‌ی تیم پیوند موجودیت

## ۱۴۰۵/۰۷/۰۳
- تصمیم گرفتیم برای نسخه‌ی فارسی سامانه، مدل ReFinED را پایه قرار دهیم، چون روی
  یک کارت T4 هم سریع اجرا می‌شود.
- آستانه‌ی NIL برای متن‌های فارسی ۰٫۴۵ تعیین شد.

## ۱۴۰۵/۰۷/۱۰
- بودجه‌ی برچسب‌گذاری داده‌ی فارسی ۱۲۰ میلیون ریال است.
- قرار شد ۶۰۰ جمله‌ی خبری فارسی برچسب بخورد؛ هر برچسب‌گذار روزانه ۴۰ جمله را بررسی می‌کند
  و سه برچسب‌گذار داریم.
- مسئول گزارش نهایی: مریم.
"""


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

CHART_VALUES = [("ReFinED", 297), ("BLINK bi-encoder", 48), ("BLINK cross-encoder", 4.9), ("CLINK cross-encoder", 6.2)]


def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def write_chart():
    width, height = 900, 520
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    draw.text((40, 20), "Mentions linked per second on one T4 GPU (our benchmark, 2026-10-01)", fill="black", font=font(20))
    left, bottom, top = 120, 450, 80
    top_value = 320
    for v in range(0, top_value + 1, 40):
        y = bottom - (bottom - top) * v / top_value
        draw.line((left, y, width - 40, y), fill="#dddddd")
        draw.text((60, y - 9), str(v), fill="black", font=font(14))
    bar_w, gap = 120, 52
    for i, (name, value) in enumerate(CHART_VALUES):
        x0 = left + gap + i * (bar_w + gap)
        y0 = bottom - (bottom - top) * value / top_value
        draw.rectangle((x0, y0, x0 + bar_w, bottom), fill="#2e7d32")
        draw.text((x0, y0 - 22), f"{value:g}", fill="black", font=font(15))
        draw.text((x0 - 10, bottom + 10), name, fill="black", font=font(13))
    draw.line((left, top, left, bottom), fill="black")
    draw.line((left, bottom, width - 40, bottom), fill="black")
    img.save(SOURCES / "throughput_chart.png")


def write_table_image_crop():
    pdf = pdfium.PdfDocument(SOURCES / "refined.pdf")
    page = pdf[5]
    scale = 3
    image = page.render(scale=scale).to_pil()
    page_h = page.get_height()
    textpage = page.get_textpage()
    searcher = textpage.search("Time taken in seconds", match_case=True)
    found = searcher.get_next()
    if not found:
        raise RuntimeError("Table 5 caption not found")
    index, _ = found
    _, cap_bottom, _, _ = textpage.get_charbox(index)
    searcher = textpage.search("Method Time taken", match_case=True)
    header = searcher.get_next()
    _, _, _, head_top = textpage.get_charbox(header[0])
    x0, x1 = 300, page.get_width() - 40
    crop = image.crop((int(x0 * scale), int((page_h - head_top - 6) * scale), int(x1 * scale), int((page_h - cap_bottom + 22) * scale)))
    crop.save(SOURCES / "refined_table5.png")


def main():
    runs = write_runs()
    audit = write_audit()
    (SOURCES / "nil_threshold.py").write_text(NIL_THRESHOLD_PY)
    (SOURCES / "recall_at_k.py").write_text(RECALL_AT_K_PY)
    (SOURCES / "latency_estimate.ts").write_text(LATENCY_TS)
    (SOURCES / "lab_notes.md").write_text(LAB_NOTES_MD)
    (SOURCES / "yaddasht-ha.md").write_text(YADDASHT_MD)
    write_chart()
    write_table_image_crop()
    print(f"runs: {len(runs)} rows, audit: {len(audit)} rows")


if __name__ == "__main__":
    main()
