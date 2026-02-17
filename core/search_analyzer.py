"""
検索分析モジュール
- Google Custom Search APIでallintitle検索（競合件数）
- 時間指定検索（鮮度判定）
- ドメイン判定（スナイパー判定用）
"""

import logging
import time
from typing import Optional, List

import requests

logger = logging.getLogger(__name__)

CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


def _search(
    query: str,
    api_config: dict,
    config: dict,
    extra_params: Optional[dict] = None,
) -> dict:
    """
    Custom Search API共通リクエスト

    Args:
        query: 検索クエリ
        api_config: APIキー設定
        config: グローバル設定
        extra_params: 追加パラメータ

    Returns:
        APIレスポンスのdict
    """
    api_key = api_config.get("google_custom_search", {}).get("api_key", "")
    cx = api_config.get("google_custom_search", {}).get("search_engine_id", "")
    timeout = config.get("timeouts", {}).get("custom_search_api", 15)
    wait = config.get("rate_limit", {}).get("wait_seconds", 1.0)

    if not api_key or not cx:
        logger.error("Custom Search APIのAPIキーまたはSearch Engine IDが未設定です")
        return {}

    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
    }
    if extra_params:
        params.update(extra_params)

    try:
        resp = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        time.sleep(wait)
        return data
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 429:
            logger.error("Custom Search API レート制限に達しました")
        elif resp.status_code == 403:
            logger.error(f"Custom Search API 認証エラー: {resp.text}")
            logger.debug(f"  api_key: {api_key[:10] if api_key else 'EMPTY'}...")
            logger.debug(f"  cx: {cx if cx else 'EMPTY'}")
            logger.error("→ APIキー、Search Engine ID、または無料枠を確認してください")
        else:
            logger.error(f"Custom Search API HTTPエラー ({resp.status_code}): {e}")
        time.sleep(wait)
        return {}
    except requests.exceptions.Timeout:
        logger.warning(f"Custom Search API タイムアウト: '{query}'")
        time.sleep(wait)
        return {}
    except requests.exceptions.RequestException as e:
        logger.warning(f"Custom Search API 通信エラー: '{query}' ({e})")
        time.sleep(wait)
        return {}


def get_allintitle_count(
    keyword: str, api_config: dict, config: dict
) -> int:
    """
    allintitle検索結果の件数を取得

    Args:
        keyword: 検索キーワード
        api_config: APIキー設定
        config: グローバル設定

    Returns:
        検索結果件数（エラー時は-1）
    """
    query = f"allintitle:{keyword}"
    data = _search(query, api_config, config)

    if not data:
        return -1

    total = int(
        data.get("searchInformation", {}).get("totalResults", 0)
    )
    logger.debug(f"allintitle '{keyword}': {total}件")
    return total


def get_recent_results(
    keyword: str, days: int, api_config: dict, config: dict
) -> dict:
    """
    指定期間内の検索結果を取得

    Args:
        keyword: 検索キーワード
        days: 期間（日数）
        api_config: APIキー設定
        config: グローバル設定

    Returns:
        {
            'count': 件数,
            'items': [{'title': str, 'link': str, 'domain': str}, ...]
        }
    """
    extra_params = {"dateRestrict": f"d{days}"}
    data = _search(keyword, api_config, config, extra_params)

    if not data:
        return {"count": 0, "items": []}

    total = int(
        data.get("searchInformation", {}).get("totalResults", 0)
    )
    items = []
    for item in data.get("items", []):
        items.append(
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "domain": item.get("displayLink", ""),
            }
        )

    return {"count": total, "items": items}


def check_domain_match(
    results: dict, target_domains: List[str]
) -> bool:
    """
    結果が全てtarget_domainsに含まれるかチェック（スナイパー判定用）

    Args:
        results: get_recent_results() の返り値
        target_domains: 監視対象ドメインのリスト

    Returns:
        True: 全ての結果がtarget_domainsに含まれる
    """
    items = results.get("items", [])
    if not items:
        return False

    for item in items:
        domain = item.get("domain", "")
        if not any(td in domain for td in target_domains):
            return False
    return True
