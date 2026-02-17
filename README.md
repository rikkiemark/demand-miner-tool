# Demand Miner Tool

**SEO キーワード需要掘削ツール** - 競合が少なく需要があるキーワードを自動発掘するツール

Google Suggest API を活用したスマート再帰掘りアルゴリズムにより、従来の総当たり方式（約5,400回）と比較して API コール数を約700〜1,000回に削減しながら、高品質なキーワードを発見します。

## Features

- **スマート再帰掘り（Route A）**: Root キーワードからサジェストを再帰的に取得し、感情キーワードでフィルタリングして有望な枝だけを深掘り
- **総当たり組み合わせ（Route B）**: Google トレンド × ワード群の全組み合わせからサジェストを網羅的に取得
- **SS〜C ランク自動判定**: allintitle 競合数 + 投稿鮮度に基づく5段階ランク付け
- **Smart TTL キャッシュ**: ランク別にキャッシュ有効期限を最適化し、API コストを抑制
- **プロファイルシステム**: ジャンル別（恋愛、AI技術 等）に設定・ワード群を管理
- **Gradio GUI**: ブラウザベースの操作画面、Google Colab にも対応

## Architecture

```
demand_miner_tool/
├── main.py                  # エントリーポイント
├── requirements.txt
├── config/
│   ├── settings.yaml        # グローバル設定（レート制限、キャッシュ、タイムアウト）
│   ├── api_keys.yaml.example
│   └── api_keys.yaml        # APIキー（.gitignore対象）
├── core/
│   ├── profile_manager.py   # プロファイル読み込み・バリデーション
│   ├── suggest_fetcher.py   # サジェスト取得（スマート再帰掘り / 総当たり）
│   ├── trend_fetcher.py     # Google トレンド急上昇ワード取得
│   ├── search_analyzer.py   # Custom Search API（allintitle / 時間指定検索）
│   ├── ranker.py            # SS/S/A/B/C ランク判定
│   └── cache_manager.py     # JSON キャッシュ管理（Smart TTL）
├── gui/
│   └── gradio_app.py        # Gradio GUI
├── profiles/
│   ├── _template/           # 新規プロファイル作成用テンプレート
│   └── romance/             # 恋愛ジャンル（サンプル）
│       ├── settings.yaml
│       └── data/
│           ├── seeds.txt       # 種キーワード（彼氏、元彼、復縁...）
│           ├── emotions.txt    # 感情キーワード（既読無視、蛙化、辛い...）
│           ├── connectors.txt  # 補助ワード（結婚、匂わせ、熱愛...）
│           └── sites.txt       # 監視対象ドメイン
├── cache/                   # キャッシュファイル（.gitignore対象）
├── outputs/                 # 結果CSV（.gitignore対象）
└── colab_setup.ipynb        # Google Colab 用セットアップノートブック
```

## How It Works

### Route A: スマート再帰掘り

```
彼氏（Root）
 └─ Google Suggest → [彼氏 既読無視, 彼氏 プレゼント, 彼氏 蛙化, ...]
     │
     ├─ 感情フィルター → "既読無視" を含む → 深掘り対象
     │   └─ "彼氏 既読無視" → Google Suggest → [彼氏 既読無視 3日, ...]
     │       └─ さらに深掘り（最大3階層）
     │
     └─ "プレゼント" → 感情キーワード不一致 → スキップ（API節約）
```

### Route B: 総当たり組み合わせ

```
トレンドワード × 補助ワード × 感情ワード の全組み合わせ
  → 各組み合わせで Google Suggest 取得
```

### ランク判定

| Rank | Condition | Action |
|------|-----------|--------|
| **SS** | allintitle 1〜5件 + 全て監視ドメイン + 24h以内に投稿あり | 即座に記事作成 |
| **S** | allintitle 0件 or 90日以上更新なし | 優先的に記事作成 |
| **A** | 30日以上更新なし | 記事作成候補 |
| **B** | 7日以上更新なし | 様子見 |
| **C** | 上記以外（競合多数） | 撤退推奨 |

### Smart TTL キャッシュ

ランクに応じてキャッシュ有効期限を自動調整：

| Rank | TTL | Reason |
|------|-----|--------|
| SS / S | 0h（毎回チェック） | お宝キーワードは常に最新状態を維持 |
| A | 24h | 1日1回の再チェックで十分 |
| B | 48h | 変動が少ないため2日間キャッシュ |
| C | 168h（1週間） | レッドオーシャンは再チェック不要 |

## Setup

### Requirements

- Python 3.9+
- pip

### 1. Install Dependencies

```bash
cd demand_miner_tool
python3 -m pip install -r requirements.txt
```

### 2. Configure API Keys (Optional)

```bash
cp config/api_keys.yaml.example config/api_keys.yaml
```

`config/api_keys.yaml` を編集し、Google Custom Search API の API キーと Search Engine ID を設定します。

```yaml
google_custom_search:
  api_key: "YOUR_API_KEY_HERE"
  search_engine_id: "YOUR_SEARCH_ENGINE_ID_HERE"
```

> **Note:** API キーがなくてもサジェスト取得機能（Route A / Route B）は動作します。ランク判定（allintitle 検索）のみ API キーが必要です。

> **Note:** Google Custom Search JSON API は現在新規ユーザーの受付を停止しています（2025年2月時点）。申請フォームからリクエスト可能です。

### 3. Launch

```bash
python3 main.py
```

ブラウザが自動で開き、GUI が表示されます（http://localhost:7860）。

### Google Colab

```bash
python3 main.py --share
```

または `colab_setup.ipynb` を Google Colab にアップロードして実行してください。

## Usage

### Preset Mode (Recommended)

1. プロファイルを選択（例: `romance`）
2. 「プリセットパターン」を選択
3. パターンを選ぶ:
   - **定番ルート**: スマート再帰掘り（Route A）
   - **トレンドルート**: 総当たり（Route B）
   - **すべて実行**: 両方を実行
4. 「分析開始」をクリック

### Custom Mode

1. プロファイルを選択
2. 「カスタムモード」を選択
3. マイニングモード（スマート再帰掘り / 総当たり）を選択
4. ワード群を自由に組み合わせて設定
5. 「分析開始」をクリック

### Output

分析結果は CSV ファイルとして `outputs/<profile_name>/results/` に保存されます。

```csv
rank,keyword,allintitle_count,route
S,彼氏 既読無視 3日,0,定番ルート（スマート再帰掘り）
A,元彼 蛙化 心理,2,定番ルート（スマート再帰掘り）
```

## Adding a New Profile

```bash
cp -r profiles/_template profiles/your_genre
```

`profiles/your_genre/settings.yaml` を編集し、`data/` フォルダにワードファイル（1行1ワード）を配置してください。

### Profile Structure

```yaml
name: "ジャンル名"

word_groups:
  seeds:
    name: "種"
    file: "data/seeds.txt"
  emotions:
    name: "切り口"
    file: "data/emotions.txt"

preset_patterns:
  - id: "route_a"
    mining_mode: "smart_recursive"
    root: "seeds"
    filter: "emotions"
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--no-cache` | キャッシュを無視して全キーワードを再取得 |
| `--share` | 公開リンクを生成（Google Colab 用） |
| `--port N` | ポート番号を指定（デフォルト: 7860） |

## Configuration

### Global Settings (`config/settings.yaml`)

```yaml
rate_limit:
  wait_seconds: 1.0          # API リクエスト間の待機時間

mining:
  mode: "smart_recursive"
  max_recursion_depth: 3      # スマート再帰掘りの最大深度

cache:
  enabled: true
  ttl_hours: 24               # デフォルト TTL
  smart_ttl:
    enabled: true              # ランク別 TTL の有効化

batch:
  checkpoint_interval: 100    # N件ごとにキャッシュを中間保存
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.9+ |
| GUI | Gradio 4.36 |
| Suggest API | Google Suggest (Unofficial) |
| Trend Data | pytrends |
| Competition Analysis | Google Custom Search JSON API |
| Configuration | YAML |
| Cache | JSON (file-based) |

## License

MIT
