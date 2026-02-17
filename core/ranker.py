"""
ランク判定モジュール
- SS/S/A/B/C ランクの判定ロジック
- プロファイル設定の閾値に基づく判定
"""

import logging

from . import search_analyzer

logger = logging.getLogger(__name__)


def determine_rank(
    keyword: str,
    allintitle_count: int,
    recent_results: dict,
    target_domains: list[str],
    ranking_config: dict,
    sniper_config: dict,
) -> str:
    """
    キーワードのランクを判定

    ランク定義:
        SS（スナイパー）: allintitle 1-max_competitors件 かつ
                        全てsites.txtドメイン かつ
                        hours_threshold以内に投稿あり
        S: allintitle 0件 または rank_s_days以上更新なし
        A: rank_a_days以上更新なし
        B: rank_b_days以上更新なし
        C: 上記以外（撤退推奨）

    Args:
        keyword: キーワード
        allintitle_count: allintitle検索結果件数
        recent_results: 各期間の検索結果
            {
                '1d': {'count': int, 'items': [...]},
                '7d': {'count': int, 'items': [...]},
                '30d': {'count': int, 'items': [...]},
                '90d': {'count': int, 'items': [...]},
            }
        target_domains: 監視対象ドメインのリスト
        ranking_config: ランク判定閾値設定
            {'rank_s_days': 90, 'rank_a_days': 30, 'rank_b_days': 7}
        sniper_config: スナイパーモード設定
            {'enabled': True, 'max_competitors': 5, 'hours_threshold': 24}

    Returns:
        'SS' | 'S' | 'A' | 'B' | 'C'
    """
    rank_s_days = ranking_config.get("rank_s_days", 90)
    rank_a_days = ranking_config.get("rank_a_days", 30)
    rank_b_days = ranking_config.get("rank_b_days", 7)

    # SSランク判定（スナイパーモード）
    if sniper_config.get("enabled", False):
        max_comp = sniper_config.get("max_competitors", 5)
        if 1 <= allintitle_count <= max_comp:
            results_1d = recent_results.get("1d", {})
            if results_1d.get("count", 0) > 0:
                if search_analyzer.check_domain_match(results_1d, target_domains):
                    logger.info(f"SSランク（スナイパー）: '{keyword}'")
                    return "SS"

    # Sランク: allintitle 0件 または 長期間更新なし
    if allintitle_count == 0:
        logger.debug(f"Sランク（競合ゼロ）: '{keyword}'")
        return "S"

    results_90d = recent_results.get(f"{rank_s_days}d", recent_results.get("90d", {}))
    if results_90d.get("count", 0) == 0:
        logger.debug(f"Sランク（{rank_s_days}日以上更新なし）: '{keyword}'")
        return "S"

    # Aランク: 一定期間更新なし
    results_30d = recent_results.get(f"{rank_a_days}d", recent_results.get("30d", {}))
    if results_30d.get("count", 0) == 0:
        logger.debug(f"Aランク（{rank_a_days}日以上更新なし）: '{keyword}'")
        return "A"

    # Bランク: 短期間更新なし
    results_7d = recent_results.get(f"{rank_b_days}d", recent_results.get("7d", {}))
    if results_7d.get("count", 0) == 0:
        logger.debug(f"Bランク（{rank_b_days}日以上更新なし）: '{keyword}'")
        return "B"

    # Cランク: 上記以外
    logger.debug(f"Cランク（撤退推奨）: '{keyword}'")
    return "C"


def analyze_keyword(
    keyword: str,
    api_config: dict,
    config: dict,
    profile_settings: dict,
    target_domains: list[str],
) -> dict:
    """
    1つのキーワードを完全に分析（allintitle + 時間指定検索 + ランク判定）

    Args:
        keyword: 分析対象キーワード
        api_config: APIキー設定
        config: グローバル設定
        profile_settings: プロファイル設定
        target_domains: 監視対象ドメインのリスト

    Returns:
        {
            'keyword': str,
            'allintitle_count': int,
            'rank': str,
            'recent_results': dict,
        }
    """
    ranking_config = profile_settings.get("ranking", {})
    sniper_config = profile_settings.get("sniper", {})
    filtering = profile_settings.get("filtering", {})

    # allintitle取得
    allintitle = search_analyzer.get_allintitle_count(keyword, api_config, config)

    # フィルタリング: allintitle件数が上限超えなら即C判定
    max_allintitle = filtering.get("max_allintitle_results", 0)
    if max_allintitle > 0 and allintitle > max_allintitle:
        return {
            "keyword": keyword,
            "allintitle_count": allintitle,
            "rank": "C",
            "recent_results": {},
        }

    # 各期間の検索結果を取得
    rank_s_days = ranking_config.get("rank_s_days", 90)
    rank_a_days = ranking_config.get("rank_a_days", 30)
    rank_b_days = ranking_config.get("rank_b_days", 7)

    recent_results = {}

    # スナイパーモード用の1日検索
    if sniper_config.get("enabled", False):
        recent_results["1d"] = search_analyzer.get_recent_results(
            keyword, 1, api_config, config
        )

    # 短い期間から順にチェック（早期打ち切り可能）
    results_7d = search_analyzer.get_recent_results(
        keyword, rank_b_days, api_config, config
    )
    recent_results[f"{rank_b_days}d"] = results_7d

    if results_7d.get("count", 0) == 0:
        # 7日で0件なら30日・90日も0件のはず（API節約のためスキップ可）
        recent_results[f"{rank_a_days}d"] = {"count": 0, "items": []}
        recent_results[f"{rank_s_days}d"] = {"count": 0, "items": []}
    else:
        results_30d = search_analyzer.get_recent_results(
            keyword, rank_a_days, api_config, config
        )
        recent_results[f"{rank_a_days}d"] = results_30d

        if results_30d.get("count", 0) == 0:
            recent_results[f"{rank_s_days}d"] = {"count": 0, "items": []}
        else:
            recent_results[f"{rank_s_days}d"] = search_analyzer.get_recent_results(
                keyword, rank_s_days, api_config, config
            )

    rank = determine_rank(
        keyword=keyword,
        allintitle_count=allintitle,
        recent_results=recent_results,
        target_domains=target_domains,
        ranking_config=ranking_config,
        sniper_config=sniper_config,
    )

    return {
        "keyword": keyword,
        "allintitle_count": allintitle,
        "rank": rank,
        "recent_results": recent_results,
    }
