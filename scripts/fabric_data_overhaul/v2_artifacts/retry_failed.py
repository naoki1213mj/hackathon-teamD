"""Retry just the failed prompts with longer timeout."""
import json
import sys
import time
import uuid
import subprocess
from pathlib import Path

WORKSPACE_ID = "096ff72a-6174-4aba-8f0c-140454fa6c3f"
DA_V2_ID = "b85b67a4-bac4-4852-95e1-443c02032844"
BASE_URL = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/dataagents/{DA_V2_ID}/aiassistant/openai"

# Re-run only timeouts and tool errors (P10, P13, P14)
RETRY_PROMPTS = [
    ("P10", "年別の売上トレンドを教えてください"),
    ("P13", "円安後の海外売上回復の度合いを教えてください"),
    ("P14", "インバウンド比率の四半期推移を教えてください"),
]
TIMEOUT_S = 360


def get_token():
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource",
         "https://analysis.windows.net/powerbi/api", "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True, check=True
    )
    return r.stdout.strip()


def run_one(qid, question):
    from openai import OpenAI
    token = get_token()
    activity_id = str(uuid.uuid4())
    client = OpenAI(
        base_url=BASE_URL, api_key="dummy",
        default_headers={
            "Authorization": f"Bearer {token}", "Accept": "application/json",
            "ActivityId": activity_id, "x-ms-workload-resource-moniker": activity_id,
            "x-ms-ai-assistant-scenario": "aiskill", "x-ms-ai-aiskill-stage": "production",
        },
        default_query={"api-version": "2024-05-01-preview"}, timeout=TIMEOUT_S,
    )
    t0 = time.time()
    try:
        assistant = client.beta.assistants.create(model="not used")
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(thread_id=thread.id, role="user", content=question)
        run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant.id)
        terminal = {"completed", "failed", "cancelled", "requires_action", "expired"}
        deadline = time.time() + TIMEOUT_S
        while run.status not in terminal:
            if time.time() > deadline:
                break
            time.sleep(2)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        elapsed = round(time.time() - t0, 1)
        if run.status != "completed":
            err = getattr(run, "last_error", None)
            try:
                client.beta.threads.delete(thread.id)
            except Exception:
                pass
            return {"qid": qid, "question": question, "status": run.status, "answer": None, "elapsed_s": elapsed, "error": str(err)}

        msgs = client.beta.threads.messages.list(thread_id=thread.id, order="asc")
        chunks = []
        for m in msgs:
            if m.role == "assistant":
                for c in m.content:
                    if hasattr(c, "text"):
                        chunks.append(c.text.value)
        answer = "\n".join(chunks).strip()
        try:
            client.beta.threads.delete(thread.id)
        except Exception:
            pass
        return {"qid": qid, "question": question, "status": "completed", "answer": answer, "elapsed_s": elapsed}
    except Exception as ex:
        return {"qid": qid, "question": question, "status": "exception", "answer": None,
                "elapsed_s": round(time.time() - t0, 1), "error": f"{type(ex).__name__}:{ex}"}


def main():
    out = []
    for qid, q in RETRY_PROMPTS:
        print(f"\n=== {qid}: {q}")
        r = run_one(qid, q)
        print(f"  → status={r['status']} {r['elapsed_s']}s")
        if r.get('answer'):
            print(f"  preview: {r['answer'][:600]}")
        else:
            print(f"  error: {r.get('error')}")
        out.append(r)
    Path("retry_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nWrote retry_results.json")


if __name__ == "__main__":
    main()
