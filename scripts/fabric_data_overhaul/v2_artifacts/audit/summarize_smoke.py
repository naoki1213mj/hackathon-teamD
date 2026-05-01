"""既存 smoke_results_*.json から各 prompt の status / grade を一覧表示する。"""
import json
from pathlib import Path

FILES = [
    "smoke_baseline_pre_phase10.json",
    "smoke_results_v6.json",
    "smoke_results_v6_postonto.json",
    "smoke_results_v6_after_ontology.json",
    "smoke_results_v6_extended.json",
    "smoke_results_v6_retry.json",
    "smoke_results_v6_retry2.json",
    "smoke_after_phase10_enrich.json",
    "smoke_after_phase10_tune.json",
]
base = Path(__file__).parent.parent
for fn in FILES:
    p = base / fn
    if not p.exists():
        continue
    print(f"=== {fn} ===")
    arr = json.loads(p.read_text(encoding="utf-8"))
    grade_counts = {"A": 0, "B": 0, "C": 0}
    for r in arr:
        qid = r.get("qid")
        st = r.get("status", "?")
        g = r.get("grade", "?")
        rea = (r.get("reason") or "")[:60]
        print(f"  {qid} {st:12s} grade={g:2s} {rea}")
        grade_counts[g] = grade_counts.get(g, 0) + 1
    print(f"  TOTAL: A={grade_counts['A']} B={grade_counts['B']} C={grade_counts['C']}")
