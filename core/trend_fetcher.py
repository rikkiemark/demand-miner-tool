"""
トレンドワード取得モジュール
- pytrendsでGoogleトレンドの急上昇ワードを取得（Bルート用）
"""

import logging
import time

logger = logging.getLogger(__name__)


def fetch_trending_keywords(config: dict, limit: int = 20) -> list[str]:
    """
    Googleトレンドから日本の急上昇ワードを取得

    Args:
        config: グローバル設定
        limit: 取得する最大件数

    Returns:
        急上昇ワードのリスト
    """
    timeout = config.get("timeouts", {}).get("trends_api", 20)
    wait = config.get("rate_limit", {}).get("wait_seconds", 1.0)

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(timeout, timeout))
        df = pytrends.trending_searches(pn="japan")
        keywords = df[0].tolist()

        if limit > 0:
            keywords = keywords[:limit]

        logger.info(f"トレンドワード取得: {len(keywords)}件")
        time.sleep(wait)
        return keywords

    except ImportError:
        logger.error(
            "pytrendsがインストールされていません。"
            "pip install pytrends を実行してください。"
        )
        return []
    except Exception as e:
        logger.error(f"トレンドワード取得エラー: {e}")
        time.sleep(wait)
        return []
