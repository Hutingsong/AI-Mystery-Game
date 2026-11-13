"""活动室谜案：消失的海报 —— Streamlit 前端。运行：streamlit run app.py"""

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.game_state import load_config, new_game
from src.npc_engine import NPCResponder

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

st.set_page_config(page_title="活动室谜案", page_icon="🕵️", layout="wide")


@st.cache_resource
def get_config():
    return load_config(str(ROOT / "config" / "game_config.json"))


@st.cache_resource
def get_responder(_config):
    return NPCResponder(_config)


def init_session(config):
    if "state" not in st.session_state:
        st.session_state.state = new_game(config)
        st.session_state.last_result = None


def render_sidebar(config, state, responder):
    st.sidebar.title("🕵️ 活动室谜案")
    st.sidebar.caption(f"模式：{responder.mode}")

    st.sidebar.subheader("📋 已解锁线索")
    if state.unlocked_clues:
        for cid in state.unlocked_clues:
            clue = config["clues"][cid]
            with st.sidebar.expander(f"{cid} · {clue['title']}"):
                st.write(clue["content"])
    else:
        st.sidebar.info("还没有解锁任何线索，先去找人聊聊。")

    st.sidebar.divider()
    st.sidebar.subheader("🎯 提交推理")
    st.sidebar.caption(f"已用次数：{state.attempts}/{config['win_condition']['max_attempts']}")

    with st.sidebar.form("answer_form"):
        direct_options = config["answer_options"]["direct"]
        root_options = config["answer_options"]["root_cause"]
        direct = st.selectbox("直接责任人", list(direct_options.keys()),
                              format_func=lambda k: direct_options[k])
        root = st.selectbox("根本原因", list(root_options.keys()),
                            format_func=lambda k: root_options[k])
        submitted = st.form_submit_button("提交", disabled=state.finished)
        if submitted:
            result = state.submit_answer(direct, root)
            st.session_state.last_result = result

    if st.session_state.get("last_result"):
        r = st.session_state.last_result
        if r["status"] == "win":
            st.sidebar.success(r["message"])
        elif r["status"] == "retry":
            st.sidebar.warning(r["message"])
        elif r["status"] == "lose":
            st.sidebar.error(r["message"])

    if state.finished:
        with st.sidebar.expander("🔍 查看真相"):
            st.write(config["truth"]["summary"])

    st.sidebar.divider()
    if st.sidebar.button("🔄 重新开始"):
        st.session_state.clear()
        st.rerun()


def render_main(config, state, responder):
    st.title(config["title"])
    st.write(config["intro"])

    if state.finished:
        if state.win:
            st.success("🎉 你推理正确，通关了！")
        else:
            st.error("❌ 两次机会用完了，本局结束。")
        st.info(f"真相：{config['truth']['summary']}")

    tabs = st.tabs([
        f"{npc['name']}（{npc['role']}）"
        for npc in config["npcs"].values()
    ])

    for tab, (npc_id, npc) in zip(tabs, config["npcs"].items()):
        with tab:
            st.caption(f"性格：{npc['personality']}")

            for msg in state.npc_histories[npc_id]:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            if state.finished:
                st.caption("本局已结束，点击侧边栏“重新开始”再玩。")
                continue

            col1, col2 = st.columns([5, 1])
            with col1:
                user_input = st.text_input(
                    "你的问题",
                    key=f"input_{npc_id}",
                    placeholder=f"问{npc['name']}点什么……",
                    label_visibility="collapsed",
                )
            with col2:
                send = st.button("发送", key=f"btn_{npc_id}", use_container_width=True)

            if send and user_input.strip():
                msg = user_input.strip()
                state.add_history(npc_id, "user", msg)

                result = responder.respond(npc_id, msg, state)
                state.add_history(npc_id, "assistant", result["reply"])

                if result["unlock_clue"]:
                    state.unlock(result["unlock_clue"])
                    st.toast(f"🔓 解锁线索 {result['unlock_clue']}", icon="✅")

                st.rerun()


def main():
    config = get_config()
    responder = get_responder(config)
    init_session(config)

    state = st.session_state.state
    render_sidebar(config, state, responder)
    render_main(config, state, responder)


if __name__ == "__main__":
    main()