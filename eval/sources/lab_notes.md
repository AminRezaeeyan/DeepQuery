# Entity linking reading group: notes

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
