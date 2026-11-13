🚀 **在线试玩地址：[点击这里直接玩](https://ai-mystery-game-f9wxxk2cnut9xyc4gzvjhb.streamlit.app)**
# 活动室谜案：消失的海报

一个 LLM 驱动的侦探推理文字游戏。玩家通过询问 4 个 NPC 获取 8 条线索，
查明海报文件被覆盖的直接原因和根本原因。

## 技术点
- 游戏状态机：线索解锁、前置条件、答题次数
- NPC 知识边界：每个 NPC 只知道自己该知道的
- 防泄露后处理：未解锁线索的关键实体不出现在回复中
- 双模式：无 API Key 走规则引擎，有 Key 走大模型
- 20 条评估用例：解锁正确率 + 泄露率

## 运行

```bash
pip install -r requirements.txt
cp .env.example .env   # 可选，填了 API Key 才用大模型
streamlit run app.py
