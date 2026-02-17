"""
Demand Miner Tool - エントリーポイント
SEOキーワード需要掘削ツール
"""

import argparse
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.gradio_app import create_interface


def main():
    parser = argparse.ArgumentParser(
        description="Demand Miner Tool - SEOキーワード需要掘削ツール"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="キャッシュを無視して強制的に全キーワードを再取得",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Gradioの公開リンクを生成（Google Colab等で使用）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="サーバーのポート番号（デフォルト: 7860）",
    )
    args = parser.parse_args()

    demo = create_interface(force_no_cache=args.no_cache)
    demo.launch(
        server_name="0.0.0.0",
        server_port=args.port,
        share=args.share,
        inbrowser=True,
    )


if __name__ == "__main__":
    main()
