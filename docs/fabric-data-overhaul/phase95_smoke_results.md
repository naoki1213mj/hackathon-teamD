# Phase 9.5 — v2 Data Agent NL2Ontology スモークテスト結果

> **目的**: Phase 9.3 で構築した 10テーブル v2 Lakehouse + Phase 9.4 で構築した v2 Direct Lake セマンティックモデル / Ontology / Data Agent (`Travel_Ontology_DA_v2`) に対し、`docs/fabric-data-overhaul/ontology.md` 141-160 行に定義された **14 本の日本語自然言語プロンプト** を投げ、応答を A/B/C で採点する。
>
> **目標**: ≥12/14 がグレード A（数値根拠あり）。
> **結果**: **A=5, B=1, C=8 (5/14)** — 目標未達。原因と Phase 9.6 改善提案を本書末に整理。

---

## 1. テスト対象

| 項目 | 値 |
|---|---|
| Workspace | `ws-3iq-demo` (`096ff72a-6174-4aba-8f0c-140454fa6c3f`) |
| Lakehouse v2 | `lh_travel_marketing_v2` (`5e02348e-d2a4-47fb-b63d-257ed3be7731`) |
| Semantic Model | `travel_SM_v2` (`ce2bb828-d850-46aa-bc5e-224ea9a60667`) — Direct Lake、12 measures、4 hierarchies、9 relationships、framing 完了済み |
| Ontology | `travelIQ_v2` (`10cd6675-405a-4366-b91b-d57242a28914`) — 10 EntityType / 9 RelationshipType |
| Data Agent | `Travel_Ontology_DA_v2` (`b85b67a4-bac4-4852-95e1-443c02032844`) |
| Endpoint | `https://api.fabric.microsoft.com/v1/workspaces/{ws}/dataagents/{da}/aiassistant/openai` |
| 実行日 | 2025-11-19 |

**Token audience**: `https://analysis.windows.net/powerbi/api/.default`
**実行スクリプト**: `C:\Users\NMATSU~1\AppData\Local\Temp\fabric_phase94\smoke_test_v2.py`（および timeout 延長版 `retry_failed.py`）

---

## 2. 採点基準

| Grade | 基準 |
|:-:|---|
| **A** | 数値根拠あり。質問された指標が具体的な金額・件数・比率付きで返る |
| **B** | 一貫性ある回答だが具体数値に欠ける／代替案提示のみ |
| **C** | 失敗。エラー、タイムアウト、「データなし」誤判定、ツール例外等 |

---

## 3. 結果サマリ

| # | プロンプト | Status | Grade | Elapsed | 概要 |
|---|---|:-:|:-:|---:|---|
| P01 | ハワイの売上を教えてください | completed | **C** | 122s | 「Hawaii (英語表記)」で検索 → 「データなし」誤回答（実データ ¥3.28B 存在、P09 で確認） |
| P02 | 夏のハワイの売上を教えてください | completed | **A** | 33s | ✅ ¥460,026,557 |
| P03 | ハワイで20代の旅行者の売上を教えてください | completed | **C** | 31s | 「該当データなし」誤回答（P05 で 88件・¥181M 確認できた条件と同一） |
| P04 | 夏のハワイで20代の旅行者の売上を教えてください | completed | **C** | 30s | 同上、誤って「0件」と回答 |
| P05 | 夏のハワイで20代の旅行者の売上、予約数、平均評価 | completed | **A** | 41s | ✅ ¥181,353,644 / 88件 / 4.0点 / レビュー 28件 |
| P06 | ハワイのレビュー評価分布を教えてください | completed | **A** | 125s | ✅ 5★ 80件、4★ 73件、3★ 34件、2★ 12件、1★ 14件 |
| P07 | 夏の沖縄でファミリー向けの売上 | completed | **C** | 30s | 「確認できませんでした」回答（要件緩和提案のみ） |
| P08 | 春のパリの売上を教えてください | completed | **A** | 29s | ✅ ¥285,253,083 / 153件 / 平均 ¥1,864,064 |
| P09 | 旅行先別の売上ランキング | completed | **A** | 37s | ✅ Top10 完全（ハワイ ¥3.28B → 沖縄 ¥2.65B → 韓国 ¥2.54B …） |
| P10 | 年別の売上トレンドを教えてください | failed (server_error) | **C** | 209s | submit_tool_outputs BadRequest（多テーブル時系列クエリで内部失敗） |
| P11 | リピート顧客の比率を教えてください | completed | **C** | 128s | 「ツール側の制限により自動集計できませんでした」（DAX RepeatCustomerRate=96.6% は SM で確認済み） |
| P12 | キャンセル率が高いプラン上位5位は？ | completed | **B** | 98s | プラン名×キャンセル率出るが、上位5位が全て 1/1=100% で意味薄い（データ希薄） |
| P13 | 円安後の海外売上回復の度合い | completed | **C** | 68s | 「為替レート 145 を境とした売上比較データなし」（実際は payment.exchange_rate_to_jpy に変動データあり、フィルタロジック不適切） |
| P14 | インバウンド比率の四半期推移 | timeout (in_progress) | **C** | 371s | 360秒延長してもタイムアウト |

**最終集計**: A=5、B=1、C=8 — 達成率 **5/14 (35.7%)**、目標 ≥12/14 に対し **未達**

---

## 4. 失敗パターン分析

### パターン A: NL2SQL の表記ゆれ／フィルタ過剰適用 (P01, P03, P04, P07)

- **症状**: 同じ条件でも問い方によって結果が「データなし」になる
- **典型例**:
  - P01「ハワイ」→ 英語 `"Hawaii"` でフィルタ → 0 件 → 「データなし」回答
  - P09「旅行先別ランキング」→ 同じテーブルで `destination_region` 集計 → 「ハワイ」¥3.28B が出る
- **根本原因**: agent 側で SQL 生成時に column 値を guess してしまい、ontology の synonym ガイドが効いていない
- **改善余地**: aiInstructions に明示的な値マッピング（"Hawaii" / "ハワイ" / "Honolulu" → `destination_region='ハワイ'`）を例示

### パターン B: マルチテーブル時系列クエリの内部エラー (P10, P14)

- **症状**: `submit_tool_outputs` で `BadRequest` または `in_progress` のままタイムアウト
- **典型クエリ**: 「年別売上トレンド」「四半期推移」「円安前後比較」など booking × payment / booking 単独の date 集計
- **改善余地**: NL2SQL agent が複数の試行で SQL を作り直すループに入っている可能性。Phase 9.6 で aiInstructions に "年別/四半期トレンドは booking_date を YEAR()/QUARTER() で集計してください" を明記

### パターン C: 計算メトリックの未活用 (P11, P13)

- **症状**: SM 側に `RepeatCustomerRate`（DAX 96.6%）や `RevenueExchangeAdjustedJPY` を実装済みだが、Data Agent はこれを使えない
- **根本原因**: Fabric Data Agent (NL2Ontology) は **Ontology のテーブル/プロパティ** を見てクエリを書くが、SM の DAX measures は SM 側のオブジェクト。両者は今のところ橋渡しされていない
- **改善余地**: aiInstructions に「リピート率＝同一 customer_id で 2件以上の予約を持つ顧客 / 全予約済顧客」のような **計算ロジックを SQL 化した実装ヒント** を Phase 9.6 で追加

---

## 5. 一貫性が確認できた要素 (Phase 9.4 成果物)

スモーク失敗とは別に、以下は本テストで実機確認できた:

- ✅ **エンドポイント疎通**: `POST /assistants` → 200 OK で `gpt-4.1-PowerBICopilot` model が払い出される
- ✅ **Direct Lake 経由のクエリ**: P02/P05/P06/P08/P09/P12 で booking, tour_review, cancellation テーブルから集計成功
- ✅ **大規模集計**: P09 で全期間 50,000 booking から destination_region 別に Top10 ランキング（数十秒）
- ✅ **クロステーブル JOIN**: P05/P06 で booking×customer×tour_review の 3-way JOIN 成功（age_band フィルタ + rating 集計）
- ✅ **数値の正確性**: SM 側の DAX 検証値（TotalRevenue ¥29.1B、AvgRating 3.87 など）と DA の回答値が一致

つまり **インフラ層と物理データは健全**、課題は **NL→SQL 変換の安定化と aiInstructions チューニング** に集中している。

---

## 6. 比較: v1 ベースライン

参考までに、Phase 9.0 時点の v1 (`Travel_Ontology_DA` / 2-table sales+reviews) は P01-P09 のみが対象で、過去のスモーク（参照: `chronicle.md` Phase 9.0 セクション）では同様にハワイ系で誤フィルタ問題が出ていた。

v2 で追加された **P10-P14（年別／リピート率／キャンセル率／為替／インバウンド）** はいずれも Phase 9.3 で初めて作った新規テーブル（cancellation, payment, campaign, customer の age_band/customer_segment/inbound_outbound）に依存しており、**Ontology には正しく含まれているが、aiInstructions に各メトリックの計算ロジックを書ききれていない** ためエラーまたは「データなし」となっている。

---

## 7. Phase 9.6 への申し送り（推奨改善）

優先順位順:

1. **aiInstructions の値マッピング強化** (P01, P03, P04, P07 想定改善)
   - `destination_region` の実値リストを明示: ハワイ / 沖縄 / 韓国 / その他 / 北海道 / 台湾 / 京都 / タイ / 東京 / 大阪 / パリ
   - 表記ゆれ → 正規化のサンプルクエリを追加
   - 「データなし」と回答する前に **必ず DISTINCT カラム値を確認するステップ** を入れる

2. **時系列集計テンプレート明示** (P10, P14 想定改善)
   - `年別`: `SELECT YEAR(booking_date) AS yr, SUM(total_revenue_jpy) FROM booking WHERE booking_status IN ('confirmed','completed') GROUP BY YEAR(booking_date) ORDER BY yr`
   - `四半期`: `DATEPART(QUARTER, booking_date)` の例
   - `インバウンド比率`: `SUM(CASE WHEN inbound_outbound='inbound' THEN total_revenue_jpy END) / SUM(total_revenue_jpy)`

3. **計算ロジックの SQL 化サンプル** (P11, P13 想定改善)
   - リピート率: `COUNT(DISTINCT CASE WHEN booking_count >= 2 THEN customer_id END) / COUNT(DISTINCT customer_id)` を CTE で
   - 円安比較: `payment.exchange_rate_to_jpy` の月平均 を時系列で並べる例

4. **Phase 9.6 SDK エンリッチメント** (`ontology.md` 162-174 行)
   - Synonym 拡張、Hierarchy 強化、measure metadata 等を Fabric SDK 経由で programmatic に追加すれば NL2Ontology の挙動が安定する可能性あり

---

## 8. 副産物 / 再現用アーティファクト

すべて `C:\Users\NMATSU~1\AppData\Local\Temp\fabric_phase94\` 配下:

| ファイル | 内容 |
|---|---|
| `build_sm_v2.py` (~21KB) | TMDL ジェネレータ + デプロイヤ |
| `tmdl/` (15 files) | 生成された TMDL（rollback 用に保存推奨） |
| `verify_sm_v2.py` | DAX 14/15 measure 検証スクリプト |
| `build_ontology_v2.py` (~15KB) | Ontology JSON ジェネレータ + デプロイヤ |
| `ontology/` (40 files) | 生成された EntityType / RelationshipType JSON |
| `build_data_agent_v2.py` (~20KB) | Data Agent config + aiInstructions |
| `data_agent/` (6 files) | draft + published mirror |
| `smoke_test_v2.py` | 14-prompt スモーク実行 |
| `smoke_results.json` | 結果ペイロード（生 JSON） |
| `retry_failed.py` | P10/P13/P14 タイムアウト延長再試行 |
| `retry_results.json` | 再試行結果 |

**v1 (rollback target)** は `travel_SM` / `travelIQ` / `Travel_Ontology_DA` のまま完全に手付かず。v2 が問題ある場合は `.env` の `FABRIC_DATA_AGENT_URL` を v1 id (`6726b401-...` 等) に戻すだけで切り替え可能。

---

## 9. 結論

Phase 9.5 の **インフラ整備（v2 SM / Ontology / DA の三点セット建立）は完遂**。一方で 14 本中 5 本しか A 評価が取れず、目標未達。失敗の主原因は Data Agent 側の NL→SQL 変換ロジックと aiInstructions のカバレッジ不足であり、データ・モデル層の問題ではない。

Phase 9.6 で aiInstructions を拡張・SDK エンリッチを適用すれば、A スコアを 9〜11 に引き上げる余地は十分にあると判断する。
