"""游戏状态管理：已解锁线索、每个NPC的对话历史、答题次数。"""

import json


class GameState:
    def __init__(self, config: dict):
        self.config = config
        self.unlocked_clues: list[str] = []
        self.npc_histories: dict[str, list[dict]] = {
            npc_id: [] for npc_id in config["npcs"]
        }
        self.attempts = 0
        self.finished = False
        self.win = False

    def unlock(self, clue_id: str | None) -> bool:
        if not clue_id:
            return False
        if clue_id in self.unlocked_clues:
            return False
        if clue_id not in self.config["clues"]:
            return False
        self.unlocked_clues.append(clue_id)
        return True

    def add_history(self, npc_id: str, role: str, content: str) -> None:
        self.npc_histories[npc_id].append({"role": role, "content": content})

    def submit_answer(self, direct: str, root_cause: str) -> dict:
        if self.finished:
            return {"status": "finished", "message": "本局已结束，点“重新开始”再玩一次。"}

        self.attempts += 1
        correct = self.config["win_condition"]["correct_answer"]
        is_right = (direct == correct["direct"] and root_cause == correct["root_cause"])

        if is_right:
            self.finished = True
            self.win = True
            return {"status": "win", "message": "推理正确！真相水落石出。"}

        if self.attempts >= self.config["win_condition"]["max_attempts"]:
            self.finished = True
            self.win = False
            return {
                "status": "lose",
                "message": "两次机会用完了。点击“查看真相”看完整复盘。",
            }

        missing = [
            c for c in self.config["win_condition"]["required_clues"]
            if c not in self.unlocked_clues
        ]
        hint = "线索不足或推理有误，再想想。"
        if missing:
            hint = f"你还有 {len(missing)} 条关键线索没拿到，先继续调查吧。"
        return {"status": "retry", "message": hint, "missing": missing}

    def to_dict(self) -> dict:
        return {
            "unlocked_clues": self.unlocked_clues,
            "attempts": self.attempts,
            "finished": self.finished,
            "win": self.win,
        }


def load_config(path: str = "config/game_config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def new_game(config: dict) -> GameState:
    return GameState(config)