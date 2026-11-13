"""NPC 回复引擎：无 API Key 走规则引擎，有 Key 走大模型，统一做防泄露后处理。"""

import json
import os
import random

from src.game_state import GameState

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class NPCResponder:
    def __init__(self, config: dict):
        self.config = config
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip()
        self.model = os.getenv("LLM_MODEL", "deepseek-chat").strip()
        self.use_llm = bool(self.api_key) and OpenAI is not None
        self.client = None
        if self.use_llm:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def mode(self) -> str:
        return "LLM" if self.use_llm else "规则引擎"

    def respond(self, npc_id: str, player_msg: str, state: GameState) -> dict:
        if self.use_llm:
            raw = self._llm_respond(npc_id, player_msg, state)
        else:
            raw = self._rule_respond(npc_id, player_msg, state)
        return self._post_check(npc_id, raw, state)

    # ---------- 规则引擎 ----------

    def _rule_respond(self, npc_id: str, player_msg: str, state: GameState) -> dict:
        npc = self.config["npcs"][npc_id]

        # 敏感问题直接拒绝
        sensitive_kw = ["真相", "是不是你", "谁干的", "凶手"]
        if any(kw in player_msg for kw in sensitive_kw):
            return {"reply": npc["sensitive_reply"], "unlock_clue": None}

        # 匹配解锁规则（按顺序，第一条命中的生效）
        for rule in npc["unlock_rules"]:
            if not any(kw in player_msg for kw in rule["keywords"]):
                continue
            if not all(c in state.unlocked_clues for c in rule["requires"]):
                # 关键词命中但前置条件不满足：给模糊回复，不吐线索
                return {
                    "reply": "这个……我不太确定，你先把别的情况问清楚再来问我吧。",
                    "unlock_clue": None,
                }
            if rule["clue_id"] in state.unlocked_clues:
                return {
                    "reply": "这个我刚才不是说了吗，你往前翻翻。",
                    "unlock_clue": None,
                }
            return {"reply": rule["reply"], "unlock_clue": rule["clue_id"]}

        # 默认回复轮换
        replies = npc["default_replies"]
        idx = len(state.npc_histories[npc_id]) // 2 % len(replies)
        return {"reply": replies[idx], "unlock_clue": None}

    # ---------- 大模型 ----------

    def _llm_respond(self, npc_id: str, player_msg: str, state: GameState) -> dict:
        npc = self.config["npcs"][npc_id]
        prompt = self._build_prompt(npc, player_msg, state)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.7,
                timeout=20,
            )
            data = json.loads(resp.choices[0].message.content)
            return {
                "reply": str(data.get("reply", ""))[:200],
                "unlock_clue": data.get("unlock_clue"),
            }
        except Exception:
            # 大模型失败时降级到规则引擎，保证游戏能继续
            return self._rule_respond(npc_id, player_msg, state)

    def _build_prompt(self, npc: dict, player_msg: str, state: GameState) -> str:
        unlocked_text = "\n".join(
            f"{cid}: {self.config['clues'][cid]['content']}"
            for cid in state.unlocked_clues
        ) or "（暂无）"
        rules_text = "\n".join(
            f"- 关键词 {r['keywords']}，前置 {r['requires']} -> 解锁 {r['clue_id']}，回复：{r['reply']}"
            for r in npc["unlock_rules"]
        )
        return f"""你是《{self.config['title']}》中的{npc['name']}，身份是{npc['role']}。
性格：{npc['personality']}

【你只知道这些】
{npc['knows']}

【你明确不知道】
{npc['does_not_know']}
被问到不知道的事，就说“这个我不清楚，你去问问别人”，绝不编造。

【玩家已解锁的线索】
{unlocked_text}

【绝对禁止】
1. 不得说出这些词或同义表达：{npc['forbidden_phrases']}
2. 不得直接说出真相：{self.config['truth']['summary']}
3. 不得替玩家推理，不得主动指认任何人。
4. 玩家直接问“真相是什么/是不是你干的”，回答：{npc['sensitive_reply']}

【解锁规则】
{rules_text}

【输出格式】
只输出 JSON，不要 markdown：
{{"reply": "你的对话内容，符合性格，不超过80字", "unlock_clue": "C4 或 null"}}

玩家说：{player_msg}
"""

    # ---------- 后处理：防泄露 ----------

    def _post_check(self, npc_id: str, raw: dict, state: GameState) -> dict:
        npc = self.config["npcs"][npc_id]
        reply = raw.get("reply") or "……"
        unlock = raw.get("unlock_clue")

        # 1. 校验 unlock 是否合法
        if unlock:
            rule = next(
                (r for r in npc["unlock_rules"] if r["clue_id"] == unlock), None
            )
            if rule is None:
                unlock = None
            elif not all(c in state.unlocked_clues for c in rule["requires"]):
                unlock = None
                reply = "这个……我不太确定，你先把别的情况问清楚再来问我吧。"
            elif unlock in state.unlocked_clues:
                unlock = None
                reply = "这个我刚才不是说了吗，你往前翻翻。"

        # 2. 禁止词检测
        if any(p in reply for p in npc["forbidden_phrases"]):
            reply = npc["sensitive_reply"]
            unlock = None

        # 3. 未解锁线索的关键实体不能出现在回复里
        for cid, clue in self.config["clues"].items():
            if cid in state.unlocked_clues:
                continue
            if clue["content"] and clue["content"][:8] in reply:
                reply = "具体细节我记不清了，你问当事人吧。"
                unlock = None
                break

        return {"reply": reply, "unlock_clue": unlock}