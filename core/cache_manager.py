"""
キャッシュ管理モジュール
- プロファイル別JSONキャッシュの読み書き
- TTL（Time To Live）制御
- Smart TTL（ランク別有効期限）
- チェックポイント保存（中断・再開用）
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "cache")


def _cache_path(profile_name: str) -> str:
    """キャッシュファイルのパスを返す"""
    return os.path.join(CACHE_DIR, profile_name, "keyword_cache.json")


def load_cache(profile_name: str) -> dict:
    """
    キャッシュファイルを読み込み、存在しなければ空辞書を返す

    Args:
        profile_name: プロファイル名

    Returns:
        キャッシュデータ dict
    """
    path = _cache_path(profile_name)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"キャッシュファイルの読み込みに失敗: {path} ({e})")
        return {}


def save_cache(profile_name: str, cache_data: dict):
    """
    キャッシュファイルに保存

    Args:
        profile_name: プロファイル名
        cache_data: 保存するキャッシュデータ
    """
    path = _cache_path(profile_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"キャッシュファイルの保存に失敗: {path} ({e})")


def is_cache_valid(
    cache_entry: dict, ttl_hours: int, smart_ttl_config: Optional[dict] = None
) -> bool:
    """
    キャッシュが有効期限内かチェック

    Args:
        cache_entry: キャッシュエントリ（timestamp, rank 含む）
        ttl_hours: 基本TTL（時間単位）
        smart_ttl_config: Smart TTL設定
            {
                'enabled': True,
                'rank_c_ttl_hours': 168,
                'rank_b_ttl_hours': 48,
                'rank_a_ttl_hours': 24,
                'rank_s_ttl_hours': 0,
                'rank_ss_ttl_hours': 0,
            }

    Returns:
        True: キャッシュ有効、False: 再取得が必要
    """
    timestamp_str = cache_entry.get("timestamp")
    if not timestamp_str:
        return False

    try:
        cached_time = datetime.fromisoformat(timestamp_str)
    except ValueError:
        return False

    # Smart TTL: ランク別に有効期限を変える
    effective_ttl = ttl_hours
    if smart_ttl_config and smart_ttl_config.get("enabled"):
        rank = cache_entry.get("rank", "").upper()
        rank_ttl_map = {
            "SS": smart_ttl_config.get("rank_ss_ttl_hours", 0),
            "S": smart_ttl_config.get("rank_s_ttl_hours", 0),
            "A": smart_ttl_config.get("rank_a_ttl_hours", 24),
            "B": smart_ttl_config.get("rank_b_ttl_hours", 48),
            "C": smart_ttl_config.get("rank_c_ttl_hours", 168),
        }
        if rank in rank_ttl_map:
            effective_ttl = rank_ttl_map[rank]

    # TTL 0 は「毎回チェック」を意味する
    if effective_ttl == 0:
        return False

    expiry = cached_time + timedelta(hours=effective_ttl)
    return datetime.now() < expiry


def get_cached_result(
    keyword: str, cache_data: dict, config: dict
) -> Optional[dict]:
    """
    キーワードのキャッシュを取得（有効期限チェック含む）

    Args:
        keyword: キーワード
        cache_data: キャッシュデータ全体
        config: グローバル設定（cache セクション）

    Returns:
        キャッシュデータ（有効な場合）、None（無効または存在しない場合）
    """
    entry = cache_data.get(keyword)
    if entry is None:
        return None

    cache_config = config.get("cache", {})
    if not cache_config.get("enabled", True):
        return None

    ttl_hours = cache_config.get("ttl_hours", 24)
    smart_ttl = cache_config.get("smart_ttl")

    if is_cache_valid(entry, ttl_hours, smart_ttl):
        return entry
    return None


def update_cache(keyword: str, result_data: dict, cache_data: dict):
    """
    キャッシュに新しい結果を追加・更新（タイムスタンプ自動付与）

    Args:
        keyword: キーワード
        result_data: 保存するデータ（allintitle_count, rank, recent_results等）
        cache_data: キャッシュデータ全体（この dict が直接更新される）
    """
    result_data["timestamp"] = datetime.now().isoformat()
    cache_data[keyword] = result_data


def checkpoint_save(
    profile_name: str,
    cache_data: dict,
    processed_count: int,
    interval: int = 100,
):
    """
    チェックポイント保存（指定件数ごとにキャッシュを保存）

    Args:
        profile_name: プロファイル名
        cache_data: キャッシュデータ
        processed_count: 処理済み件数
        interval: 保存間隔

    Returns:
        保存した場合はTrue
    """
    if interval > 0 and processed_count > 0 and processed_count % interval == 0:
        save_cache(profile_name, cache_data)
        logger.info(f"チェックポイント保存: {processed_count}件処理済み")
        return True
    return False
