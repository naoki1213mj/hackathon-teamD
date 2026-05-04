<!-- Phase 11d source — see session-state/.../fabric-da-instructions-improved-draft.md for rationale -->

このデータソースは `travelIQ_v2` ontology のバックエンドと同じ 10 テーブルへの T-SQL 直アクセス経路。**個票照会 / 最新 N 件 / 存在確認** にのみ使う (KPI 集計・ランキング・期間集計は ontology 側を使う)。

## ルーティング再確認
- 「○○の売上推移」「○○ランキング」「リピート率」「平均単価」「キャンペーン ROI」「為替影響」 → ontology に委譲。本データソース直叩きで再構築しない (`booking_status IN ('confirmed','completed')` などのビジネス制約が抜けて数値が誤る)。
- 「予約コード `BK-2026-000123` の詳細」「顧客コード `C-2025-000456` の予約履歴」「直近 10 件」「○○は存在するか」 → 本データソースを使う。

## T-SQL 方言 (Fabric SQL endpoint)
- 行数制限は **`TOP (N)`** または **`OFFSET ... FETCH NEXT N ROWS ONLY`**。`LIMIT` は使えない。
- `TOP (N)` / `OFFSET ... FETCH NEXT` には **必ず `ORDER BY`** を付ける (省略すると非決定的)。tie-breaker として 2 つ目のソートキー (PK や `*_id`) を併記する (例: `ORDER BY booking_date DESC, booking_id DESC`)。
- 日本語リテラルは **`N'…'`** で Unicode 化する: `WHERE plan_name LIKE N'%沖縄%ファミリー%'`。
- スキーマ修飾は `dbo.<table>` を必須にする (`dbo` 省略不可)。
- 列名は具体列を列挙する。`SELECT *` を最終クエリで使わない。
- 書き込み (`INSERT` / `UPDATE` / `DELETE` / `MERGE` / `CREATE` / `DROP` / `TRUNCATE`) と外部送信は全面禁止。

## 値マッピング (Agent Instructions §4 の lakehouse 抜粋)
- `destination_region` は **日本語** 30 値 (`沖縄` `北海道` `京都` `ハワイ` `パリ` `ニューヨーク` `タイ` 等)。「Hawaii」と聞かれたら `destination_region = N'ハワイ'` で検索 (`destination_country='Hawaii'` は存在しない、ハワイは `'USA'`)。
- `destination_country` は **英語** 13 値。
- `season` は英語コード 7 値: `spring` / `summer` / `autumn` / `winter` / `gw` / `obon` / `new_year`。
- `customer_segment` は英語コード 7 値: `family` / `couple` / `solo` / `group` / `senior` / `student` / `business`。
- `age_band` は `10s` / `20s` / `30s` / `40s` / `50s` / `60s` / `70s+` の 7 値。
- `booking_status` は `confirmed` / `completed` / `cancelled` / `no_show` の 4 値。
- **`payment_status` は `succeeded` / `refunded` の 2 値のみ** (`pending` / `failed` は実データに存在しない)。
- 識別子コードのフォーマット例は Description 欄を参照 (`BK-{YYYY}-{NNNNNN}` / `C-{YYYY}-{NNNNNN}` / `CMP-{YYYY}-Q{1-4}-{NNN}`)。

## クエリ例
**典型クエリは "Example queries" タブで管理**: native `exampleQueries` (15 件) に登録済みの個票照会 / 最新 N 件 / 存在確認 / pagination パターンを参照。本欄に T-SQL 例文を重複記載しない。

## 出力時の注意
- UUID (`*_id`) は結合・cross-check に使い、最終回答テキストに UUID 文字列を露出させない。`booking_code` 等の人間可読コードを使う。
- `tour_review.comment` の本文は実在値のみを引用 (要約せず、最大 1〜2 件に抑える)。
- 25 行を超える raw 行 dump は禁止。
- 個票照会の結果は表形式で 1 行サマリにし、PII 推論 (年齢推定 / 居住地推定 / 属性推定) を加えない。
