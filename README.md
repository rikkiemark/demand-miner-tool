# Demand Miner Tool

**Note:** This is a personal SEO keyword analysis tool designed for the Japanese market.
It utilizes Google Suggest and Search APIs to identify niche market demands.
Currently under development and intended for personal use only.

---

## 概要

Demand Miner Tool は、SEO キーワードの需要と競合状況を分析するための個人開発ツールです。

ブログや Web メディアの運営において、「検索需要はあるが競合が少ないキーワード」を見つけることは非常に重要ですが、手動で行うと膨大な時間がかかります。本ツールはその作業を自動化し、キーワード候補の収集から競合分析・ランク判定までを一括で行います。

## 主な機能

- **キーワード候補の自動収集** — Google サジェスト API からキーワード候補を取得
- **競合分析** — DataForSEO SERP API を使って `allintitle` 検索を行い、競合記事数を取得
- **鮮度チェック** — 日付指定検索で、直近の競合記事の有無を確認
- **ランク判定** — 競合状況に基づいてキーワードを自動ランク付け（S / A / B / C）
- **プロファイル管理** — ジャンルごとにキーワードセットと設定を分離管理
- **GUI** — ブラウザベースの操作画面（Gradio）

## DataForSEO API の使用目的

本ツールでは、キーワードの競合分析に **DataForSEO Google Organic SERP API (Standard queue)** を使用します。

### 使用する API エンドポイント

| エンドポイント | 用途 |
|---|---|
| `/v3/serp/google/organic/task_post` | 検索タスクの投稿（バッチ処理） |
| `/v3/serp/google/organic/tasks_ready` | 完了タスクの確認 |
| `/v3/serp/google/organic/task_get/regular` | 検索結果の取得 |

### 具体的な使い方

1. **allintitle 検索**: `allintitle:キーワード` で検索し、タイトルにそのキーワードを含む記事の件数を取得。競合の多寡を判断する指標として使用
2. **日付指定検索**: 同じキーワードで期間を指定して検索し、直近に公開された競合記事の有無を確認

### API 利用パラメータ

- `location_code`: 2392（日本）
- `language_code`: "ja"
- `search_engine`: Google
- `type`: organic
- バッチサイズ: 最大 100 タスク/リクエスト

### 想定されるリクエスト量

個人利用のため、1 回の分析で数百〜数千キーワードを処理します。キャッシュ機能により、同一キーワードへの再リクエストは抑制されます。

## 動作環境

| 項目 | 要件 |
|------|------|
| OS | macOS / Windows / Linux |
| Python | 3.9 以上 |
| 必須 API | なし（サジェスト取得のみなら API キー不要） |
| 任意 API | DataForSEO Google Organic SERP API（競合分析に必要） |

## セットアップ

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# API キーの設定（DataForSEO を使用する場合）
cp config/api_keys.yaml.example config/api_keys.yaml
# api_keys.yaml を編集して DataForSEO のログイン情報を入力

# 起動
python main.py
```

ブラウザが自動で開き、`http://localhost:7860` で GUI にアクセスできます。

### CLI オプション

```bash
python main.py [OPTIONS]
```

| オプション | 説明 |
|-----------|------|
| `--no-cache` | キャッシュを無視して全キーワードを再取得 |
| `--share` | Gradio 公開リンクを生成 |
| `--port N` | サーバーのポート番号を指定（デフォルト: 7860） |

## プロジェクト構成

```
demand_miner_tool/
├── main.py                  # エントリーポイント（GUI 起動）
├── requirements.txt         # 依存パッケージ
├── config/
│   ├── settings.yaml        # グローバル設定
│   ├── api_keys.yaml        # API キー（Git 管理対象外）
│   └── api_keys.yaml.example
├── core/                    # コアモジュール
├── gui/                     # GUI
├── profiles/                # ジャンル別プロファイル
├── cache/                   # キャッシュ（Git 管理対象外）
└── outputs/                 # 結果出力先（Git 管理対象外）
```

## ライセンス

MIT License
