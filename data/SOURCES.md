# Demo corpus — Asymptotic Safety / Quantum Einstein Gravity

The PDFs themselves are **not** committed (see `.gitignore`). Reproduce the demo
corpus by downloading these arXiv papers into `corpus/`:

```
python download_arxiv.py --ids 1202.2274 1707.09298 2504.07877 2508.00807 2509.12469 2601.20820 2605.11805
```

| arXiv ID | Title | Authors |
|---|---|---|
| 1202.2274 | Quantum Einstein Gravity | Reuter, Saueressig |
| 1707.09298 | Exact RG Flow Equations and Quantum Gravity | de Alwis |
| 2504.07877 | Gauge and parametrization dependence of QEG within the Proper Time flow | Bonanno, Oglialoro, Zappalà |
| 2508.00807 | Proper-time functional renormalization in O(N) scalar models coupled to gravity | Bonanno, Glaviano, Vacca |
| 2509.12469 | Regular Black Holes from Proper-Time flow in QG: Quasinormal modes, Shadow, Hawking radiation | Bonanno, Konoplya, Oglialoro, Spina |
| 2601.20820 | Gravitationally Induced UV Completion of an O(N) Scalar Theory | Bonanno, Glaviano |
| 2605.11805 | Scaling Solutions of Matter Form Factors in Asymptotically Safe Quantum Gravity | Bonanno, Buccio, Glaviano, Saueressig |

`test_set.json` contains 21 hand-curated question/ground-truth pairs drawn from
these papers (3 per paper), used to compute RAGAS `context_recall`.

To use a different domain, replace these PDFs with your own and rewrite
`test_set.json` (see the "Adapting to a new domain" section of the README).
