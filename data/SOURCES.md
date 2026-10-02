# Demo corpus — Asymptotic Safety / Quantum Einstein Gravity

The PDFs themselves are **not** committed (see `.gitignore`). Download these arXiv papers into `data/` (command in the README):


| arXiv ID | Title | Authors |
|---|---|---|
| 1202.2274 | Quantum Einstein Gravity | Reuter, Saueressig |
| 1707.09298 | Exact RG Flow Equations and Quantum Gravity | de Alwis |
| 2504.07877 | Gauge and parametrization dependence of QEG within the Proper Time flow | Bonanno, Oglialoro, Zappalà |
| 2508.00807 | Proper-time functional renormalization in O(N) scalar models coupled to gravity | Bonanno, Glaviano, Vacca |
| 2509.12469 | Regular Black Holes from Proper-Time flow in QG: Quasinormal modes, Shadow, Hawking radiation | Bonanno, Konoplya, Oglialoro, Spina |
| 2601.20820 | Gravitationally Induced UV Completion of an O(N) Scalar Theory | Bonanno, Glaviano |
| 2605.11805 | Scaling Solutions of Matter Form Factors in Asymptotically Safe Quantum Gravity | Bonanno, Buccio, Glaviano, Saueressig |

The 21 hand-curated question/ground-truth pairs behind the retrieval tasks in `evals/tasks.jsonl` come from
the sibling `langchain-rag-assistant` project (3 per paper).
