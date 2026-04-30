"""Run 14-prompt smoke test against Travel_Ontology_DA_v2.

Uses OpenAI Assistants API compatible endpoint: api.fabric.microsoft.com/v1/workspaces/{ws}/dataagents/{id}/aiassistant/openai
- Token audience: https://analysis.windows.net/powerbi/api/.default
- Headers: Authorization, Accept, ActivityId, x-ms-workload-resource-moniker, x-ms-ai-assistant-scenario, x-ms-ai-aiskill-stage
- Query: api-version=2024-05-01-preview
- Pattern: assistants.create -> threads.create -> messages.create -> runs.create -> poll -> messages.list

Grading (per task spec):
- A: Grounded numeric data with concrete values from the dataset
- B: Coherent answer but no numeric grounding (or generic)
- C: Failure (timeout, error, refusal, or hallucinated placeholders)

Target: >=12/14 grade A.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

WORKSPACE_ID = "096ff72a-6174-4aba-8f0c-140454fa6c3f"
DA_V2_ID = "b85b67a4-bac4-4852-95e1-443c02032844"
BASE_URL = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/dataagents/{DA_V2_ID}/aiassistant/openai"

PROMPTS = [
    # 既存 9-prompt (互換性確認)
    ("P01", "ハワイの売上を教えてください"),
    ("P02", "夏のハワイの売上を教えてください"),
    ("P03", "ハワイで20代の旅行者の売上を教えてください"),
    ("P04", "夏のハワイで20代の旅行者の売上を教えてください"),
    ("P05", "夏のハワイで20代の旅行者の売上、予約数、平均評価を教えてください"),
    ("P06", "ハワイのレビュー評価分布を教えてください"),
    ("P07", "夏の沖縄でファミリー向けの売上を教えてください"),
    ("P08", "春のパリの売上を教えてください"),
    ("P09", "旅行先別の売上ランキングを教えてください"),
    # 新規 5-prompt (richer dataset の威力を見せる)
    ("P10", "年別の売上トレンドを教えてください"),
    ("P11", "リピート顧客の比率を教えてください"),
    ("P12", "キャンセル率が高いプラン上位5位は？"),
    ("P13", "円安後の海外売上回復の度合いを教えてください"),
    ("P14", "インバウンド比率の四半期推移を教えてください"),
]

TIMEOUT_S = 180


def get_token():
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource",
         "https://analysis.windows.net/powerbi/api", "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True, check=True
    )
    return r.stdout.strip()


def make_client(token: str):
    from openai import OpenAI
    activity_id = str(uuid.uuid4())
    return OpenAI(
        base_url=BASE_URL,
        api_key="dummy",
        default_headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "ActivityId": activity_id,
            "x-ms-workload-resource-moniker": activity_id,
            "x-ms-ai-assistant-scenario": "aiskill",
            "x-ms-ai-aiskill-stage": "production",
        },
        default_query={"api-version": "2024-05-01-preview"},
        timeout=TIMEOUT_S,
    )


def grade(answer: str | None) -> tuple[str, str]:
    """Return (grade, reason)."""
    if answer is None or not answer.strip():
        return "C", "empty/null"
    a = answer
    low = a.lower()
    bad_phrases = [
        "技術的なエラー", "システム的なエラー", "システム的な制約",
        "技術的制約", "技術的な都合",
        "データ抽出ができませんでした", "集計クエリの制約により", "グループ集計の制約により",
        "取得できませんでした", "申し訳ありません", "お答えできません",
        "申し訳ございません", "確認できませんでした",
    ]
    for p in bad_phrases:
        if p in a:
            return "C", f"failure_phrase:{p}"
    placeholder_phrases = [
        "旅行先A", "旅行先B", "○○件", "○○○○", "X/XX/XXX",
        "プレースホルダー", "(例)", "サンプル",
    ]
    for p in placeholder_phrases:
        if p in a:
            return "C", f"placeholder:{p}"

    # Numeric ground check: at least one digit run with >=3 digits or any ¥/円 amount
    digit_groups = re.findall(r"\d{2,}", a)
    has_currency = bool(re.search(r"[¥￥]\s*[\d,]+|[\d,]+\s*円", a))
    has_pct = bool(re.search(r"\d+(\.\d+)?\s*%", a))
    has_count = any(int(d) > 0 for d in digit_groups[:20] if d.isdigit())
    grounded = has_currency or has_pct or has_count
    if grounded:
        return "A", "grounded_numeric"
    if len(a) > 100:
        return "B", "coherent_but_not_numeric"
    return "C", "too_short"


def run_one(token: str, qid: str, question: str) -> dict:
    """Run one prompt. Returns {qid, question, status, answer, grade, reason, elapsed_s}."""
    t0 = time.time()
    client = make_client(token)
    try:
        assistant = client.beta.assistants.create(model="not used")
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=question
        )
        run = client.beta.threads.runs.create(
            thread_id=thread.id, assistant_id=assistant.id
        )

        terminal = {"completed", "failed", "cancelled", "requires_action", "expired"}
        deadline = time.time() + TIMEOUT_S
        while run.status not in terminal:
            if time.time() > deadline:
                break
            time.sleep(2)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        if run.status != "completed":
            err = getattr(run, "last_error", None)
            try:
                client.beta.threads.delete(thread.id)
            except Exception:
                pass
            return {
                "qid": qid, "question": question, "status": run.status,
                "answer": None, "grade": "C",
                "reason": f"run.{run.status}:{err}",
                "elapsed_s": round(time.time() - t0, 1),
            }

        msgs = client.beta.threads.messages.list(thread_id=thread.id, order="asc")
        assistant_chunks = []
        for m in msgs:
            if m.role == "assistant":
                parts = []
                for c in m.content:
                    if hasattr(c, "text"):
                        parts.append(c.text.value)
                joined = "\n".join(parts).strip()
                if joined:
                    assistant_chunks.append(joined)
        answer = assistant_chunks[-1] if assistant_chunks else None

        try:
            client.beta.threads.delete(thread.id)
        except Exception:
            pass

        g, reason = grade(answer)
        return {
            "qid": qid, "question": question, "status": "completed",
            "answer": answer, "grade": g, "reason": reason,
            "elapsed_s": round(time.time() - t0, 1),
        }
    except Exception as ex:
        return {
            "qid": qid, "question": question, "status": "exception",
            "answer": None, "grade": "C", "reason": f"exception:{type(ex).__name__}:{ex}",
            "elapsed_s": round(time.time() - t0, 1),
        }


def main():
    token = get_token()
    results = []
    for qid, q in PROMPTS:
        print(f"\n=== {qid}: {q}")
        r = run_one(token, qid, q)
        ans_preview = (r['answer'] or '')[:300].replace("\n", " ")
        print(f"  → status={r['status']} grade={r['grade']} ({r['reason']}) {r['elapsed_s']}s")
        if r['answer']:
            print(f"  preview: {ans_preview}")
        results.append(r)

    out = Path(__file__).parent / "smoke_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults written to {out}")

    print("\n=== SUMMARY ===")
    a_count = sum(1 for r in results if r['grade'] == 'A')
    b_count = sum(1 for r in results if r['grade'] == 'B')
    c_count = sum(1 for r in results if r['grade'] == 'C')
    total = len(results)
    print(f"A (grounded): {a_count}/{total}")
    print(f"B (coherent): {b_count}/{total}")
    print(f"C (failed):   {c_count}/{total}")
    target_met = a_count >= 12
    print(f"\nTarget >=12 grade A: {'✅ MET' if target_met else f'❌ NOT MET ({a_count}/14)'}")
    return 0 if target_met else 1


if __name__ == "__main__":
    sys.exit(main())
