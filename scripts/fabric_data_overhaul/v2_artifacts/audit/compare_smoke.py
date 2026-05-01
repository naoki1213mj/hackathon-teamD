"""3 段階の smoke 結果を表で比較する補助スクリプト。"""
from __future__ import annotations

import collections
import json
from pathlib import Path

BASE = Path(__file__).parent.parent
FILES = {
    "baseline_pre_phase10": "smoke_baseline_pre_phase10.json",
    "after_enrich": "smoke_after_phase10_enrich.json",
    "after_tune": "smoke_after_phase10_tune.json",
}


def main() -> None:
    data: dict[str, dict[str, dict]] = {}
    for k, v in FILES.items():
        path = BASE / v
        if not path.exists():
            print(f"missing: {path}")
            continue
        arr = json.loads(path.read_text(encoding="utf-8"))
        data[k] = {r["qid"]: r for r in arr}

    qids = sorted(set().union(*[d.keys() for d in data.values()]))
    headers = list(data.keys())
    print(f"{'qid':5} " + " ".join(f"{h:25}" for h in headers))
    print("-" * (5 + 26 * len(headers)))
    for qid in qids:
        row = [qid]
        for h in headers:
            r = data[h].get(qid)
            if r is None:
                row.append("(missing)")
                continue
            row.append(f"{r['status'][:10]}|{r['grade']}")
        print(f"{row[0]:5} " + " ".join(f"{c:25}" for c in row[1:]))

    print()
    for k, d in data.items():
        cnts = collections.Counter(r["grade"] for r in d.values())
        print(f"{k}: A={cnts['A']} B={cnts['B']} C={cnts['C']}  (n={sum(cnts.values())})")


if __name__ == "__main__":
    main()
