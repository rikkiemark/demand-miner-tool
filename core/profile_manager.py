"""
プロファイル管理モジュール
- プロファイルの読み込み・バリデーション
- ワード群ファイルの読み込み
- プリセットパターンの取得
"""

import os
import yaml
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# プロジェクトルートディレクトリ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")


def list_profiles() -> List[str]:
    """
    利用可能なプロファイル一覧を取得（_template除外）

    Returns:
        プロファイル名のリスト
    """
    profiles = []
    if not os.path.isdir(PROFILES_DIR):
        return profiles
    for name in sorted(os.listdir(PROFILES_DIR)):
        if name.startswith("_") or name.startswith("."):
            continue
        profile_path = os.path.join(PROFILES_DIR, name)
        if os.path.isdir(profile_path) and os.path.exists(
            os.path.join(profile_path, "settings.yaml")
        ):
            profiles.append(name)
    return profiles


def load_word_group(group_config: dict, profile_path: str) -> List[str]:
    """
    個別のワード群ファイルを読み込む（改行区切り、空行・#コメント無視）

    Args:
        group_config: word_groupsの1つの設定（例: {'name': '種', 'file': 'data/seeds.txt'}）
        profile_path: プロファイルのルートパス

    Returns:
        ワードのリスト
    """
    file_path = os.path.join(profile_path, group_config["file"])
    if not os.path.exists(file_path):
        logger.warning(f"ワード群ファイルが見つかりません: {file_path}")
        return []

    words = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                words.append(line)
    return words


def load_profile(profile_name: str) -> dict:
    """
    プロファイルを読み込む（汎用化対応）

    Args:
        profile_name: プロファイル名（例: "romance"）

    Returns:
        {
            'settings': {
                'name': "恋愛ジャンル",
                'word_groups': {...},
                'preset_patterns': [...],
                'ranking': {...},
                'sniper': {...},
                'filtering': {...},
            },
            'word_data': {
                'seeds': ["彼氏", "元彼", ...],
                'emotions': ["既読無視", "蛙化", ...],
                ...
            }
        }

    Raises:
        FileNotFoundError: プロファイルディレクトリまたはsettings.yamlが存在しない場合
        ValueError: 設定ファイルのバリデーションに失敗した場合
    """
    profile_path = os.path.join(PROFILES_DIR, profile_name)
    settings_path = os.path.join(profile_path, "settings.yaml")

    if not os.path.isdir(profile_path):
        raise FileNotFoundError(f"プロファイルが見つかりません: {profile_path}")
    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"設定ファイルが見つかりません: {settings_path}")

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    # ワード群を読み込み
    word_data = {}
    word_groups = settings.get("word_groups", {})
    for group_id, group_config in word_groups.items():
        word_data[group_id] = load_word_group(group_config, profile_path)
        logger.info(
            f"ワード群 '{group_config.get('name', group_id)}' を読み込み: {len(word_data[group_id])}件"
        )

    return {"settings": settings, "word_data": word_data}


def get_pattern_config(pattern_id: str, profile: dict) -> Optional[dict]:
    """
    プリセットパターンIDから設定を取得

    Args:
        pattern_id: パターンID（例: "route_a"）
        profile: load_profile() の返り値

    Returns:
        パターン設定dict、見つからない場合はNone
    """
    patterns = profile["settings"].get("preset_patterns", [])
    for pattern in patterns:
        if pattern.get("id") == pattern_id:
            return pattern
    return None


def get_pattern_choices(profile: dict) -> List[Tuple[str, str]]:
    """
    GUI用のパターン選択肢を生成

    Args:
        profile: load_profile() の返り値

    Returns:
        [(表示名, パターンID), ...] のリスト
    """
    patterns = profile["settings"].get("preset_patterns", [])
    choices = []
    for p in patterns:
        label = p.get("name", p["id"])
        desc = p.get("description", "")
        if desc:
            label = f"{label} - {desc}"
        choices.append((label, p["id"]))
    return choices


def get_word_group_choices(profile: dict) -> List[Tuple[str, str]]:
    """
    GUI用のワード群選択肢を生成

    Args:
        profile: load_profile() の返り値

    Returns:
        [(表示名, グループID), ...] のリスト
    """
    word_groups = profile["settings"].get("word_groups", {})
    choices = []
    for group_id, group_config in word_groups.items():
        name = group_config.get("name", group_id)
        desc = group_config.get("description", "")
        count = len(profile["word_data"].get(group_id, []))
        label = f"{name} ({count}件)"
        if desc:
            label = f"{label} - {desc}"
        choices.append((label, group_id))
    return choices


def validate_profile(profile: dict) -> List[str]:
    """
    プロファイルの妥当性をチェック

    Args:
        profile: load_profile() の返り値

    Returns:
        エラーメッセージのリスト（空なら妥当）
    """
    errors = []
    settings = profile.get("settings", {})

    # name チェック
    if not settings.get("name"):
        errors.append("プロファイル名(name)が設定されていません")

    # word_groups チェック
    word_groups = settings.get("word_groups", {})
    if not word_groups:
        errors.append("ワード群(word_groups)が定義されていません")
    for group_id, group_config in word_groups.items():
        if "file" not in group_config:
            errors.append(f"ワード群 '{group_id}' にfileが指定されていません")
        if not profile["word_data"].get(group_id):
            errors.append(
                f"ワード群 '{group_id}' のデータが空です（ファイルが見つからないか空）"
            )

    # preset_patterns チェック
    patterns = settings.get("preset_patterns", [])
    for pattern in patterns:
        if "id" not in pattern:
            errors.append("プリセットパターンにidがありません")
            continue

        pid = pattern["id"]

        # run_multiple の場合は参照先の存在チェック
        if "run_multiple" in pattern:
            for ref_id in pattern["run_multiple"]:
                if not any(p.get("id") == ref_id for p in patterns):
                    errors.append(
                        f"パターン '{pid}' が参照する '{ref_id}' が見つかりません"
                    )
            continue

        mining_mode = pattern.get("mining_mode")
        if mining_mode == "smart_recursive":
            if "root" not in pattern:
                errors.append(
                    f"パターン '{pid}' (smart_recursive) にrootが指定されていません"
                )
            elif pattern["root"] not in word_groups:
                errors.append(
                    f"パターン '{pid}' のroot '{pattern['root']}' が word_groups に存在しません"
                )
            if "filter" not in pattern:
                errors.append(
                    f"パターン '{pid}' (smart_recursive) にfilterが指定されていません"
                )
            elif pattern["filter"] not in word_groups:
                errors.append(
                    f"パターン '{pid}' のfilter '{pattern['filter']}' が word_groups に存在しません"
                )
        elif mining_mode == "brute_force":
            combination = pattern.get("combination", [])
            if not combination:
                errors.append(
                    f"パターン '{pid}' (brute_force) にcombinationが指定されていません"
                )
            for group_ref in combination:
                if group_ref not in word_groups:
                    errors.append(
                        f"パターン '{pid}' のcombination '{group_ref}' が word_groups に存在しません"
                    )
        else:
            errors.append(
                f"パターン '{pid}' のmining_modeが不正です: {mining_mode}"
            )

    # ranking チェック
    ranking = settings.get("ranking", {})
    for key in ["rank_s_days", "rank_a_days", "rank_b_days"]:
        val = ranking.get(key)
        if val is not None and (not isinstance(val, int) or val <= 0):
            errors.append(f"ranking.{key} は正の整数である必要があります: {val}")

    return errors


def load_global_config() -> dict:
    """
    グローバル設定（config/settings.yaml）を読み込む

    Returns:
        設定dict
    """
    config_path = os.path.join(BASE_DIR, "config", "settings.yaml")
    if not os.path.exists(config_path):
        logger.warning(f"グローバル設定が見つかりません: {config_path}（デフォルト値を使用）")
        return _default_global_config()

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # デフォルト値をマージ
    defaults = _default_global_config()
    for key, val in defaults.items():
        if key not in config:
            config[key] = val
        elif isinstance(val, dict):
            for k2, v2 in val.items():
                if k2 not in config[key]:
                    config[key][k2] = v2
    return config


def load_api_keys() -> dict:
    """
    APIキー（config/api_keys.yaml）を読み込む

    Returns:
        APIキー設定dict
    """
    keys_path = os.path.join(BASE_DIR, "config", "api_keys.yaml")
    if not os.path.exists(keys_path):
        logger.warning(f"APIキーファイルが見つかりません: {keys_path}")
        return {}

    with open(keys_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _default_global_config() -> dict:
    """デフォルトのグローバル設定"""
    return {
        "rate_limit": {"wait_seconds": 1.0},
        "mining": {"mode": "smart_recursive", "max_recursion_depth": 3},
        "cache": {
            "enabled": True,
            "ttl_hours": 24,
            "smart_ttl": {
                "enabled": True,
                "rank_c_ttl_hours": 168,
                "rank_b_ttl_hours": 48,
                "rank_a_ttl_hours": 24,
                "rank_s_ttl_hours": 0,
                "rank_ss_ttl_hours": 0,
            },
        },
        "timeouts": {
            "suggest_api": 10,
            "custom_search_api": 15,
            "trends_api": 20,
        },
        "batch": {
            "enabled": True,
            "checkpoint_interval": 100,
            "max_keywords_per_run": 0,
        },
    }
