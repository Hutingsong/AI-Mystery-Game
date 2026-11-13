"""跑 20 条评估用例，统计解锁正确率和泄露率。命令行：python -m src.evaluator"""

import json
from pathlib import Path

from dotenv import load_dotenv

from src.game_state import load_config, new_game
from src.npc_engine import NPCResponder

ROOT = Path(__file__).resolve().parent.parent


def run_eval(cases_path: str = "data/eval_cases.json") -> dict:
    load_dotenv()
    config = load_config(str(ROOT / "config" / "game_config.json"))
    responder = NPCResponder(config)
    cases = json.loads((ROOT / cases_path).read_text(encoding="utf-8"))

    total = len(cases)
    unlock_ok = 0
    leak_violation = 0
    failures = []

    for case in cases:
        state = new_game(config)
        for cid in case["unlocked_before"]:
            state.unlock(cid)

        result = responder.respond(case["npc"], case["player"], state)

        got = result["unlock_clue"]
        exp = case["expect_unlock"]
        ok_unlock = (got == exp)
        if ok_unlock:
            unlock_ok += 1

        reply = result["reply"]
        must_not = case.get("must_not_contain", [])
        leaked = any(w in reply for w in must_not)
        if leaked:
            leak_violation += 1

        if not ok_unlock or leaked:
            failures.append({
                "id": case["id"],
                "npc": case["npc"],
                "player": case["player"],
                "expect_unlock": exp,
                "got_unlock": got,
                "reply": reply,
                "must_not_contain": must_not,
                "leaked": leaked,
            })

    passed = total - len(failures)
    report = {
        "mode": responder.mode,
        "total": total,
        "unlock_correct": unlock_ok,
        "unlock_rate": round(unlock_ok / total, 3),
        "leak_violation": leak_violation,
        "passed": passed,
        "pass_rate": round(passed / total, 3),
        "failures": failures,
    }
    return report


def main():
    report = run_eval()
    print(f"=== 评估结果（{report['mode']}）===")
    print(f"总用例: {report['total']}")
    print(f"解锁正确: {report['unlock_correct']}/{report['total']} ({report['unlock_rate']*100:.1f}%)")
    print(f"泄露违规: {report['leak_violation']}/{report['total']}")
    print(f"通过: {report['passed']}/{report['total']} ({report['pass_rate']*100:.1f}%)")
    if report["failures"]:
        print("\n--- 未通过用例 ---")
        for f in report["failures"]:
            print(f"[#{f['id']}] {f['npc']} | 玩家: {f['player']}")
            print(f"  期望解锁: {f['expect_unlock']} | 实际: {f['got_unlock']} | 泄露: {f['leaked']}")
            print(f"  回复: {f['reply']}\n")


if __name__ == "__main__":
    main()