"""
サジェスト取得モジュール（スマート再帰掘り対応）
- Google Suggest Webエンドポイントからサジェスト取得
- Aルート: スマート再帰掘り（smart_recursive_search）
- Bルート: 総当たり組み合わせ（brute_force_combinations）
- パターン別の統合インターフェース
"""

import itertools
import logging
import time
import urllib.parse
from typing import Optional, List

import requests

logger = logging.getLogger(__name__)

SUGGEST_URL = "http://suggestqueries.google.com/complete/search"


def fetch_suggestions(keyword: str, config: dict) -> List[str]:
    """
    指定キーワードのサジェストを取得

    Args:
        keyword: 検索キーワード
        config: グローバル設定

    Returns:
        サジェストキーワードのリスト（重複排除済み）
    """
    timeout = config.get("timeouts", {}).get("suggest_api", 10)
    wait = config.get("rate_limit", {}).get("wait_seconds", 1.0)

    params = {
        "client": "firefox",
        "q": keyword,
        "hl": "ja",
    }

    try:
        resp = requests.get(SUGGEST_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        # レスポンス形式: [クエリ, [サジェスト1, サジェスト2, ...]]
        suggestions = data[1] if len(data) > 1 else []
        # 元のキーワードそのものは除外
        suggestions = [s for s in suggestions if s.strip() != keyword.strip()]
        logger.debug(f"サジェスト取得: '{keyword}' → {len(suggestions)}件")
    except requests.exceptions.Timeout:
        logger.warning(f"サジェストAPIタイムアウト: '{keyword}'")
        suggestions = []
    except requests.exceptions.RequestException as e:
        logger.warning(f"サジェストAPI通信エラー: '{keyword}' ({e})")
        suggestions = []
    except (ValueError, IndexError, KeyError) as e:
        logger.warning(f"サジェストAPIレスポンスパースエラー: '{keyword}' ({e})")
        suggestions = []

    time.sleep(wait)
    return suggestions


def filter_by_keywords(
    suggestions: List[str], filter_keywords: List[str]
) -> List[str]:
    """
    サジェストリストから、フィルターキーワードが含まれるものだけを抽出

    Args:
        suggestions: サジェストリスト
        filter_keywords: フィルター用キーワード（例: ["既読無視", "蛙化", "辛い"]）

    Returns:
        フィルター条件に合致したサジェストのリスト
    """
    filtered = []
    for suggestion in suggestions:
        for fk in filter_keywords:
            if fk in suggestion:
                filtered.append(suggestion)
                break
    return filtered


def smart_recursive_search(
    root_keywords: List[str],
    filter_keywords: List[str],
    config: dict,
    current_depth: int = 0,
    max_depth: int = 3,
    _seen: Optional[set] = None,
    progress_callback=None,
) -> List[str]:
    """
    スマート再帰掘り：rootから始めて、filterに合致する枝だけを深掘り

    Args:
        root_keywords: 開始起点のキーワードリスト（例: ["彼氏", "元彼", "復縁"]）
        filter_keywords: フィルター条件（例: ["既読無視", "蛙化", "辛い"]）
        config: グローバル設定
        current_depth: 現在の再帰深度
        max_depth: 最大再帰深度
        _seen: 既に処理済みのキーワード（重複排除用、内部使用）
        progress_callback: 進捗コールバック（fn(message: str)）

    Returns:
        発見されたサジェストキーワードのリスト（重複排除済み）
    """
    if _seen is None:
        _seen = set()

    if current_depth >= max_depth:
        return []

    all_results = []
    next_roots = []

    depth_label = f"深度{current_depth + 1}/{max_depth}"

    for i, root in enumerate(root_keywords):
        if root in _seen:
            continue
        _seen.add(root)

        if progress_callback:
            progress_callback(
                f"[{depth_label}] サジェスト取得中: '{root}' ({i+1}/{len(root_keywords)})"
            )

        suggestions = fetch_suggestions(root, config)

        if current_depth == 0:
            # 最初の階層: フィルターで絞り込む
            matched = filter_by_keywords(suggestions, filter_keywords)
            logger.info(
                f"[{depth_label}] '{root}' → サジェスト{len(suggestions)}件, "
                f"フィルター合致{len(matched)}件"
            )
        else:
            # 2階層目以降: サジェスト全体を結果に含め、さらにフィルターで深掘り対象を選別
            matched = filter_by_keywords(suggestions, filter_keywords)
            # サジェスト自体はすべて結果に含める（深掘り対象はフィルター合致のみ）
            for s in suggestions:
                if s not in _seen:
                    all_results.append(s)

        # フィルター合致したサジェストを結果に追加し、次の深掘り対象に
        for m in matched:
            if m not in _seen:
                all_results.append(m)
                next_roots.append(m)

    # 次の階層を深掘り
    if next_roots:
        if progress_callback:
            progress_callback(
                f"[深度{current_depth + 2}/{max_depth}] 深掘り開始: {len(next_roots)}件の有望な枝"
            )
        deeper = smart_recursive_search(
            root_keywords=next_roots,
            filter_keywords=filter_keywords,
            config=config,
            current_depth=current_depth + 1,
            max_depth=max_depth,
            _seen=_seen,
            progress_callback=progress_callback,
        )
        all_results.extend(deeper)

    # 重複排除（順序保持）
    seen_results = set()
    unique = []
    for r in all_results:
        if r not in seen_results:
            seen_results.add(r)
            unique.append(r)
    return unique


def brute_force_combinations(
    word_groups: List[List[str]],
    use_trend: bool = False,
    trend_words: Optional[List[str]] = None,
) -> List[str]:
    """
    総当たり組み合わせ生成（Bルート用）

    Args:
        word_groups: ワード群のリスト（例: [["結婚", "匂わせ"], ["辛い", "羨ましい"]]）
        use_trend: トレンドを含めるか
        trend_words: トレンドワードのリスト

    Returns:
        組み合わせキーワードのリスト（例: ["大谷翔平 結婚 辛い", ...]）
    """
    if use_trend and trend_words:
        all_groups = [trend_words] + word_groups
    else:
        all_groups = word_groups

    if not all_groups:
        return []

    combinations = []
    for combo in itertools.product(*all_groups):
        keyword = " ".join(combo)
        combinations.append(keyword)

    logger.info(f"総当たり組み合わせ生成: {len(combinations)}件")
    return combinations


def fetch_suggestions_for_combinations(
    keywords: List[str],
    config: dict,
    progress_callback=None,
) -> List[str]:
    """
    キーワードリストの各要素についてサジェストを取得し、全結果をまとめる

    Args:
        keywords: 組み合わせキーワードのリスト
        config: グローバル設定
        progress_callback: 進捗コールバック

    Returns:
        サジェストキーワードのリスト（重複排除済み）
    """
    all_suggestions = []
    seen = set()

    for i, kw in enumerate(keywords):
        if progress_callback:
            progress_callback(
                f"サジェスト取得中: '{kw}' ({i+1}/{len(keywords)})"
            )
        suggestions = fetch_suggestions(kw, config)
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                all_suggestions.append(s)

    return all_suggestions


def fetch_suggestions_for_pattern(
    pattern: dict,
    profile_data: dict,
    config: dict,
    trend_words: Optional[List[str]] = None,
    progress_callback=None,
) -> List[str]:
    """
    プリセットパターンに基づいてサジェストを一括取得
    mining_modeに応じて smart_recursive_search または brute_force_combinations を使用

    Args:
        pattern: パターン設定（preset_patterns の1つ）
        profile_data: プロファイルデータ（word_data含む）
        config: グローバル設定
        trend_words: トレンドワードのリスト（Bルート用）
        progress_callback: 進捗コールバック

    Returns:
        サジェストキーワードのリスト（重複排除済み）
    """
    mining_mode = pattern.get("mining_mode", "smart_recursive")
    word_data = profile_data.get("word_data", {})
    max_depth = config.get("mining", {}).get("max_recursion_depth", 3)

    if mining_mode == "smart_recursive":
        # Aルート: スマート再帰掘り
        root_group = pattern.get("root", "")
        filter_group = pattern.get("filter", "")

        root_keywords = word_data.get(root_group, [])
        filter_keywords = word_data.get(filter_group, [])

        if not root_keywords:
            logger.warning(f"Rootワード群 '{root_group}' が空です")
            return []
        if not filter_keywords:
            logger.warning(f"Filterワード群 '{filter_group}' が空です")
            return []

        if progress_callback:
            progress_callback(
                f"スマート再帰掘り開始: Root={len(root_keywords)}件, "
                f"Filter={len(filter_keywords)}件, 最大深度={max_depth}"
            )

        return smart_recursive_search(
            root_keywords=root_keywords,
            filter_keywords=filter_keywords,
            config=config,
            max_depth=max_depth,
            progress_callback=progress_callback,
        )

    elif mining_mode == "brute_force":
        # Bルート: 総当たり
        combination_ids = pattern.get("combination", [])
        use_trend = pattern.get("use_trend", False)

        groups = []
        for gid in combination_ids:
            words = word_data.get(gid, [])
            if words:
                groups.append(words)
            else:
                logger.warning(f"ワード群 '{gid}' が空です")

        if not groups and not (use_trend and trend_words):
            logger.warning("組み合わせるワード群がありません")
            return []

        keywords = brute_force_combinations(
            word_groups=groups,
            use_trend=use_trend,
            trend_words=trend_words,
        )

        if progress_callback:
            progress_callback(
                f"総当たりモード: {len(keywords)}件の組み合わせからサジェスト取得開始"
            )

        return fetch_suggestions_for_combinations(
            keywords=keywords,
            config=config,
            progress_callback=progress_callback,
        )

    else:
        logger.error(f"不明なmining_mode: {mining_mode}")
        return []
