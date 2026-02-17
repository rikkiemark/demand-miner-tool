"""
Gradio GUIインターフェース
- プロファイル選択・パターン選択・カスタムモード
- 分析実行・進捗表示・結果CSV出力
"""

import csv
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Tuple, List

import gradio as gr

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    cache_manager,
    profile_manager,
    ranker,
    suggest_fetcher,
    trend_fetcher,
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _setup_logging():
    """ロギング設定"""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run_analysis(
    profile_name: str,
    mode: str,
    pattern_id: str,
    custom_use_trend: bool,
    custom_group1: str,
    custom_group2: str,
    custom_group3: str,
    custom_mining_mode: str,
    force_no_cache: bool = False,
    progress=gr.Progress(track_tqdm=False),
) -> Tuple[str, Optional[str], str]:
    """
    分析を実行

    Returns:
        (結果サマリー, CSVファイルパス, ログテキスト)
    """
    log_lines = []

    def log(msg):
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        logger.info(msg)

    def progress_cb(msg):
        log(msg)
        progress(0, desc=msg)

    try:
        # プロファイル読み込み
        log(f"プロファイル読み込み中: {profile_name}")
        profile = profile_manager.load_profile(profile_name)

        # バリデーション
        errors = profile_manager.validate_profile(profile)
        if errors:
            error_msg = "プロファイルのバリデーションエラー:\n" + "\n".join(
                f"  - {e}" for e in errors
            )
            log(error_msg)
            return error_msg, None, "\n".join(log_lines)

        # グローバル設定読み込み
        config = profile_manager.load_global_config()
        api_config = profile_manager.load_api_keys()

        # キャッシュ無効化
        if force_no_cache:
            config.setdefault("cache", {})["enabled"] = False
            log("キャッシュ無効化モード")

        settings = profile["settings"]
        word_data = profile["word_data"]
        target_domains = word_data.get("sites", [])

        # ワード群サマリー表示
        for gid, words in word_data.items():
            gname = settings.get("word_groups", {}).get(gid, {}).get("name", gid)
            log(f"  {gname}: {len(words)}件")

        # パターン解決
        patterns_to_run = []
        if mode == "preset":
            pattern_config = profile_manager.get_pattern_config(pattern_id, profile)
            if not pattern_config:
                return f"パターン '{pattern_id}' が見つかりません", None, "\n".join(
                    log_lines
                )
            # run_multiple の展開
            if "run_multiple" in pattern_config:
                for pid in pattern_config["run_multiple"]:
                    p = profile_manager.get_pattern_config(pid, profile)
                    if p:
                        patterns_to_run.append(p)
            else:
                patterns_to_run.append(pattern_config)
        else:
            # カスタムモード: 動的にパターン設定を生成
            groups_selected = [
                g for g in [custom_group1, custom_group2, custom_group3] if g
            ]
            if not groups_selected:
                return "ワード群を1つ以上選択してください", None, "\n".join(log_lines)

            if custom_mining_mode == "smart_recursive" and len(groups_selected) >= 2:
                patterns_to_run.append(
                    {
                        "id": "custom",
                        "name": "カスタム（スマート再帰掘り）",
                        "mining_mode": "smart_recursive",
                        "root": groups_selected[0],
                        "filter": groups_selected[1],
                        "use_trend": custom_use_trend,
                    }
                )
            else:
                patterns_to_run.append(
                    {
                        "id": "custom",
                        "name": "カスタム（総当たり）",
                        "mining_mode": "brute_force",
                        "combination": groups_selected,
                        "use_trend": custom_use_trend,
                    }
                )

        # トレンドワード取得（必要な場合のみ）
        trend_words = None
        if any(p.get("use_trend") for p in patterns_to_run):
            log("トレンドワード取得中...")
            trend_words = trend_fetcher.fetch_trending_keywords(config)
            if trend_words:
                log(f"トレンドワード: {len(trend_words)}件取得")
                log(f"  例: {', '.join(trend_words[:5])}")
            else:
                log("トレンドワードの取得に失敗しました")

        # サジェスト取得
        all_suggestions = []
        for pat in patterns_to_run:
            pname = pat.get("name", pat.get("id", ""))
            log(f"パターン実行: {pname}")

            suggestions = suggest_fetcher.fetch_suggestions_for_pattern(
                pattern=pat,
                profile_data=profile,
                config=config,
                trend_words=trend_words,
                progress_callback=progress_cb,
            )
            log(f"  サジェスト取得結果: {len(suggestions)}件")
            all_suggestions.extend(suggestions)

        # 重複排除
        seen = set()
        unique_suggestions = []
        for s in all_suggestions:
            if s not in seen:
                seen.add(s)
                unique_suggestions.append(s)
        log(f"サジェスト合計（重複排除後）: {len(unique_suggestions)}件")

        if not unique_suggestions:
            return "サジェストが取得できませんでした", None, "\n".join(log_lines)

        # キャッシュ読み込み
        cache_data = cache_manager.load_cache(profile_name)
        cache_hits = 0
        api_calls = 0

        # 各キーワードを分析
        results = []
        total = len(unique_suggestions)
        checkpoint_interval = config.get("batch", {}).get(
            "checkpoint_interval", 100
        )

        for i, keyword in enumerate(unique_suggestions):
            pct = (i + 1) / total
            progress(pct, desc=f"分析中: {i+1}/{total} ({pct*100:.1f}%)")

            # キャッシュチェック
            cached = cache_manager.get_cached_result(keyword, cache_data, config)
            if cached:
                results.append(cached)
                cache_hits += 1
                continue

            # API実行
            if not api_config.get("google_custom_search", {}).get("api_key"):
                # APIキー未設定時はサジェストのみの結果を返す
                result = {
                    "keyword": keyword,
                    "allintitle_count": -1,
                    "rank": "?",
                    "recent_results": {},
                }
            else:
                result = ranker.analyze_keyword(
                    keyword=keyword,
                    api_config=api_config,
                    config=config,
                    profile_settings=settings,
                    target_domains=target_domains,
                )
                api_calls += 1

            results.append(result)

            # キャッシュ更新
            cache_manager.update_cache(keyword, result, cache_data)

            # チェックポイント保存
            cache_manager.checkpoint_save(
                profile_name, cache_data, i + 1, checkpoint_interval
            )

        # 最終キャッシュ保存
        cache_manager.save_cache(profile_name, cache_data)
        log(f"キャッシュ保存完了")
        log(f"キャッシュヒット: {cache_hits}件, 新規API実行: {api_calls}件")

        # ランク別集計
        rank_counts = {"SS": 0, "S": 0, "A": 0, "B": 0, "C": 0, "?": 0}
        for r in results:
            rank = r.get("rank", "?")
            rank_counts[rank] = rank_counts.get(rank, 0) + 1

        # CSV出力
        csv_path = _save_results_csv(profile_name, results, patterns_to_run)
        log(f"結果CSV出力: {csv_path}")

        # サマリー生成
        summary_lines = [
            f"分析完了: {len(results)}件のキーワード",
            "",
            "ランク別集計:",
        ]
        for rank in ["SS", "S", "A", "B", "C", "?"]:
            count = rank_counts.get(rank, 0)
            if count > 0:
                summary_lines.append(f"  {rank}: {count}件")

        summary_lines.extend(
            [
                "",
                f"キャッシュヒット: {cache_hits}件",
                f"新規API実行: {api_calls}件",
            ]
        )

        return "\n".join(summary_lines), csv_path, "\n".join(log_lines)

    except FileNotFoundError as e:
        log(f"エラー: {e}")
        return str(e), None, "\n".join(log_lines)
    except Exception as e:
        log(f"予期しないエラー: {e}")
        logger.exception("分析中にエラーが発生")
        return f"エラーが発生しました: {e}", None, "\n".join(log_lines)


def _save_results_csv(
    profile_name: str, results: list[dict], patterns: list[dict]
) -> str:
    """結果をCSVに保存"""
    output_dir = os.path.join(BASE_DIR, "outputs", profile_name, "results")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(output_dir, f"result_{timestamp}.csv")

    route_name = ", ".join(p.get("name", p.get("id", "")) for p in patterns)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["rank", "keyword", "allintitle_count", "route"]
        )
        for r in results:
            writer.writerow(
                [
                    r.get("rank", "?"),
                    r.get("keyword", ""),
                    r.get("allintitle_count", -1),
                    route_name,
                ]
            )

    return csv_path


def _on_profile_change(profile_name: str):
    """プロファイル変更時のコールバック"""
    if not profile_name:
        return gr.update(choices=[]), gr.update(choices=[]), "", gr.update(
            choices=[]
        ), gr.update(choices=[]), gr.update(choices=[])

    try:
        profile = profile_manager.load_profile(profile_name)
        pattern_choices = profile_manager.get_pattern_choices(profile)
        group_choices = profile_manager.get_word_group_choices(profile)

        desc = profile["settings"].get("name", profile_name)

        p_choices = [(label, pid) for label, pid in pattern_choices]
        g_choices = [("(なし)", "")] + [(label, gid) for label, gid in group_choices]

        return (
            gr.update(choices=p_choices, value=p_choices[0][1] if p_choices else None),
            gr.update(visible=True),
            f"プロファイル: {desc}",
            gr.update(choices=g_choices, value=""),
            gr.update(choices=g_choices, value=""),
            gr.update(choices=g_choices, value=""),
        )
    except Exception as e:
        return (
            gr.update(choices=[]),
            gr.update(visible=True),
            f"エラー: {e}",
            gr.update(choices=[]),
            gr.update(choices=[]),
            gr.update(choices=[]),
        )


def _on_mode_change(mode: str):
    """実行モード変更時のコールバック"""
    is_preset = mode == "preset"
    return gr.update(visible=is_preset), gr.update(visible=not is_preset)


def create_interface(force_no_cache: bool = False) -> gr.Blocks:
    """Gradioインターフェースを構築"""
    _setup_logging()

    profiles = profile_manager.list_profiles()

    with gr.Blocks(
        title="Demand Miner Tool",
        theme=gr.themes.Soft(),
    ) as demo:
        gr.Markdown("# Demand Miner Tool")
        gr.Markdown("SEOキーワード需要掘削ツール")

        with gr.Row():
            with gr.Column(scale=1):
                # プロファイル選択
                profile_dd = gr.Dropdown(
                    choices=profiles,
                    label="プロファイル選択",
                    value=profiles[0] if profiles else None,
                    interactive=True,
                )
                profile_desc = gr.Textbox(
                    label="プロファイル情報",
                    interactive=False,
                    lines=1,
                )

                # 実行モード選択
                mode_radio = gr.Radio(
                    choices=[
                        ("プリセットパターン（推奨）", "preset"),
                        ("カスタムモード（高度）", "custom"),
                    ],
                    label="実行モード",
                    value="preset",
                )

                # プリセットモード
                with gr.Group(visible=True) as preset_group:
                    pattern_dd = gr.Dropdown(
                        choices=[],
                        label="パターン選択",
                        interactive=True,
                    )

                # カスタムモード
                with gr.Group(visible=False) as custom_group:
                    custom_mining = gr.Radio(
                        choices=[
                            ("スマート再帰掘り", "smart_recursive"),
                            ("総当たり", "brute_force"),
                        ],
                        label="マイニングモード",
                        value="smart_recursive",
                    )
                    custom_trend = gr.Checkbox(
                        label="トレンドワードを含める", value=False
                    )
                    custom_g1 = gr.Dropdown(
                        choices=[], label="ワード群1 (Root/組み合わせ1)", interactive=True
                    )
                    custom_g2 = gr.Dropdown(
                        choices=[], label="ワード群2 (Filter/組み合わせ2)", interactive=True
                    )
                    custom_g3 = gr.Dropdown(
                        choices=[], label="ワード群3 (オプション)", interactive=True
                    )

                no_cache_cb = gr.Checkbox(
                    label="キャッシュを無視（強制再取得）",
                    value=force_no_cache,
                )

                run_btn = gr.Button("分析開始", variant="primary", size="lg")

            with gr.Column(scale=2):
                result_text = gr.Textbox(
                    label="結果サマリー",
                    interactive=False,
                    lines=12,
                )
                result_file = gr.File(label="結果CSVダウンロード")
                log_text = gr.Textbox(
                    label="実行ログ",
                    interactive=False,
                    lines=15,
                    max_lines=30,
                )

        # イベントハンドラ
        profile_dd.change(
            fn=_on_profile_change,
            inputs=[profile_dd],
            outputs=[
                pattern_dd,
                preset_group,
                profile_desc,
                custom_g1,
                custom_g2,
                custom_g3,
            ],
        )

        mode_radio.change(
            fn=_on_mode_change,
            inputs=[mode_radio],
            outputs=[preset_group, custom_group],
        )

        run_btn.click(
            fn=run_analysis,
            inputs=[
                profile_dd,
                mode_radio,
                pattern_dd,
                custom_trend,
                custom_g1,
                custom_g2,
                custom_g3,
                custom_mining,
                no_cache_cb,
            ],
            outputs=[result_text, result_file, log_text],
        )

        # 初期読み込み
        if profiles:
            demo.load(
                fn=_on_profile_change,
                inputs=[profile_dd],
                outputs=[
                    pattern_dd,
                    preset_group,
                    profile_desc,
                    custom_g1,
                    custom_g2,
                    custom_g3,
                ],
            )

    return demo
