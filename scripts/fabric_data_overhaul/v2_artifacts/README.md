# Phase 9.4 / 9.5 v2 アーティファクト

このディレクトリは **Phase 9.3 (10テーブル v2 Lakehouse) 構築後に Phase 9.4-9.5 で再構築した
SemanticModel / Ontology / DataAgent** の生成・デプロイ・検証スクリプト一式と、Phase 9.5 のスモークテスト結果を保存している。

## ファイル

| ファイル | 役割 |
|---|---|
| `build_sm_v2.py` | `travel_SM_v2` (Direct Lake、12 measures、4 hierarchies、9 relationships) を TMDL から生成・POST |
| `verify_sm_v2.py` | Power BI executeQueries API で 14/15 DAX measure を検証 |
| `build_ontology_v2.py` | `travelIQ_v2` (10 EntityType / 9 RelationshipType) JSON ペイロードを生成・POST |
| `build_data_agent_v2.py` | `Travel_Ontology_DA_v2` (aiInstructions 約 10KB を含む config) を生成・POST |
| `smoke_test_v2.py` | 14 本の日本語プロンプトをエージェントに投げ、A/B/C 採点 |
| `retry_failed.py` | timeout 系プロンプトを 360 秒に延長して再試行 |
| `smoke_results.json` | 14 本スモーク結果（生 JSON） |
| `retry_results.json` | 再試行結果 |
| `v2_ids.txt` | 確定した v2 item id |

## v2 Item IDs

```
Workspace:   096ff72a-6174-4aba-8f0c-140454fa6c3f  (ws-3iq-demo)
Lakehouse:   5e02348e-d2a4-47fb-b63d-257ed3be7731  (lh_travel_marketing_v2)
Semantic:    ce2bb828-d850-46aa-bc5e-224ea9a60667  (travel_SM_v2)
Ontology:    10cd6675-405a-4366-b91b-d57242a28914  (travelIQ_v2)
DataAgent:   b85b67a4-bac4-4852-95e1-443c02032844  (Travel_Ontology_DA_v2)
```

## v1 ロールバック先

v1 (`travel_SM` / `travelIQ` / `Travel_Ontology_DA`) は完全に手付かず。問題があれば
`.env` の `FABRIC_DATA_AGENT_URL` を v1 id に戻すだけで切替可能。

## Direct Lake / Ontology のハマりどころ（学び）

1. **Direct Lake framing**: TMDL POST 直後の DAX は 400 エラー。`POST /datasets/{id}/refreshes`
   (`{"type":"automatic","commitMode":"transactional"}`) を 1 回叩く必要あり。
2. **Fabric Ontology contextualization**:
   - `entityIdParts` には PK propertyId のみを入れる（FK は入れない）
   - `dataBindingTable` = source (many) 側の物理テーブル
   - `sourceKeyRefBindings`: source PK 列 → source PK propId（length = source `entityIdParts.length`）
   - `targetKeyRefBindings`: source 側にある FK 列 → target PK propId（length = target `entityIdParts.length`）
3. **Data Agent endpoint**: `https://api.fabric.microsoft.com/v1/workspaces/{ws}/dataagents/{da}/aiassistant/openai`
   （`dataagents` は小文字）。Token audience: `https://analysis.windows.net/powerbi/api/.default`。

詳細は `docs/fabric-data-overhaul/phase95_smoke_results.md` 参照。

## 再生成手順

各スクリプトの先頭に `WORKSPACE_ID` `LAKEHOUSE_ID` 等が定数定義されているので、別環境への移植時は値を書き換えて実行する。

```powershell
# 1. SemanticModel
python build_sm_v2.py

# 2. Ontology
python build_ontology_v2.py

# 3. Data Agent
python build_data_agent_v2.py

# 4. Smoke test
python smoke_test_v2.py
```

各スクリプトは Azure CLI 経由で `DefaultAzureCredential` 相当のトークンを取得する
(`az account get-access-token --resource ...`) ので、実行前に `az login` 済みであること。
