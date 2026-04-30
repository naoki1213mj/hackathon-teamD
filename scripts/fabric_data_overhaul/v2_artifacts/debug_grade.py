"""Debug strict grader on P12 answer."""
import json, re
from bestof_strict import grade2, LLM_FALLBACK, LARGE_YEN, COUNT_LARGE, PCT_REASONABLE, FAIL_PHRASES, NODATA

d = json.load(open("smoke_results_v6_after_ontology.json", "r", encoding="utf-8"))
p12 = next(r for r in d if r["qid"] == "P12")
ans = p12["answer"]

print("=== fallback hits ===")
for p in LLM_FALLBACK:
    if p in ans:
        # find context
        i = ans.find(p)
        ctx = ans[max(0, i-20):i+len(p)+20]
        print(f"  {p!r} -> ...{ctx}...")

print("\n=== large yen matches ===")
for m in LARGE_YEN.findall(ans)[:5]:
    print(" ", m)
print("\n=== count large matches ===")
for m in COUNT_LARGE.findall(ans)[:5]:
    print(" ", m)
print("\n=== pct matches ===")
for m in PCT_REASONABLE.findall(ans)[:5]:
    print(" ", m)
print("\n=== fail phrases ===")
for p in FAIL_PHRASES:
    if p in ans:
        print(f"  HIT: {p}")
print("\n=== nodata ===")
for p in NODATA:
    if p in ans:
        print(f"  HIT: {p}")
print("\n=== final grade2 ===")
g, r = grade2(ans)
print(f"{g} / {r}")
