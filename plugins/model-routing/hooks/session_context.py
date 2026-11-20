#!/usr/bin/env python3
"""model-routing: SessionStart hook.

セッション開始（startup / resume / clear / compact）時に、メイン会話の委譲ポリシーを
additionalContext として注入する。委譲ポリシーの正本はこのファイルの POLICY。
失敗しても常に exit 0（fail-open）。
"""

import json
import sys

POLICY = """\
[model-routing] メイン会話は計画・設計判断・成果物の検証を担い、実作業はサブエージェントに委譲する（Agent ツールの subagent_type はフルネーム model-routing:<name> で指定する）。
- model-routing:explorer: 所在特定・使用箇所の洗い出しなど機械的な探索。メイン会話は自分でコードベースを広く読み回らない。結果のパス・行番号は coder にそのまま渡し、二重に探索させない。
- model-routing:coder: 仕様が明確な実装・単純な修正。対象ファイル・期待する変更・完了条件を具体的に渡し、戻った成果物は必ず自分で検証する（差分確認・テスト実行）。仕様が曖昧な部分は coder に投げず、メイン会話で判断する。
- model-routing:reviewer: 実装とテストが一段落し、ユーザーに引き継ぐ直前に通す。変更範囲（diff の基点・対象ファイル）・仕様と完了条件・実行済みのテストを渡す。typo やドキュメントのみなど、ごく小さな変更では省略してよい。指摘は自分で検証してから coder に修正を委譲し、「要精査」の箇所は advisor に回す。ユーザーから明示的に依頼されたコードレビューは reviewer を使わずメイン会話が行う。
- model-routing:advisor: 同じ問題で修正→検証が 2 回失敗した / 仮説が尽きて原因を特定できない / アーキテクチャ全体に関わる設計判断、のときにエスカレーションする。問題・試したこと・失敗内容・関連パスを渡す。返った方針をもとに、実装は coder に委譲する。
- サブエージェントの出力はユーザーに直接見えないため、メイン会話が要約してユーザーに報告する。"""


def main() -> int:
    try:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": POLICY,
                    }
                },
                ensure_ascii=False,
            )
        )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
