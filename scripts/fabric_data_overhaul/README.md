# Fabric Data Overhaul: 生成スクリプト

このディレクトリは **Phase 9.2** の hybrid seeded synthetic データ生成スクリプトです。  
本番アプリ (`src/`) の依存からは隔離されており、`scripts/fabric_data_overhaul/` 内でのみ動作する standalone な Python ツールです。

## ディレクトリ構成

```text
scripts/fabric_data_overhaul/
├── README.md                    # 本ファイル
├── pyproject.toml               # standalone uv プロジェクト
├── seed_distributions.json      # 公的統計から抽出した seed (集計値のみ、PII 不混入)
├── generate_dataset.py          # メイン生成スクリプト
├── output/                      # 生成された Parquet 出力先 (.gitignore)
└── samples/                     # 各テーブルの先頭 50 行サンプル (commit する)
```

## 依存

- Python 3.14
- Faker (jp locale)
- numpy
- pandas
- pyarrow (Parquet 出力)

## 使い方

```bash
cd scripts/fabric_data_overhaul
uv sync
uv run python generate_dataset.py --output-dir output --sample-dir samples
```

実行後:
- `output/*.parquet` (10 テーブル) が Phase 9.3 の Lakehouse 投入用
- `samples/*.csv` (各 50 行) が PR レビュー / docs 用に commit される

## 設計方針

詳細は [`docs/fabric-data-overhaul/schema.md`](../../docs/fabric-data-overhaul/schema.md) と  
[`docs/fabric-data-overhaul/ontology.md`](../../docs/fabric-data-overhaul/ontology.md) を参照。

要点:
- 5 年分 (2022-01-01 〜 2026-04-30)
- COVID リバウンド・円安・GW/お盆/年末年始/春節を seasonality に反映
- 全レコード synthetic (PII 不混入、Faker 生成のダミー)
- 公的統計 (観光庁主要旅行業者の旅行取扱状況、e-Stat 宿泊旅行統計、日銀為替) は **集計分布の seed としてのみ使用**
- 決定論的な seed (`numpy.random.default_rng(42)`) で reproducible

## ロールバック戦略

このスクリプトは Lakehouse へ直接書き込みません。Parquet 出力を確認した上で  
Phase 9.3 で Spark notebook 経由で投入するため、データに問題があっても  
`output/` を削除して再生成すれば即座にリセットできます。
