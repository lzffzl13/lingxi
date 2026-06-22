"""Streamlit frontend for LingXi customer service."""

import streamlit as st
import httpx
import asyncio
from datetime import datetime

# API endpoint
API_URL = "http://localhost:8000"


def init_session():
    """Initialize session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"streamlit-{datetime.now().strftime('%Y%m%d%H%M%S')}"


async def send_message(message: str) -> dict:
    """Send message to API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_URL}/chat",
            json={
                "session_id": st.session_state.session_id,
                "message": message,
            },
            timeout=30.0,
        )
        return response.json()


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="灵犀客服",
        page_icon="💬",
        layout="wide",
    )

    st.title("💬 灵犀智能客服")
    st.caption("基于 AI 的智能客服系统")

    # Sidebar
    with st.sidebar:
        st.header("关于")
        st.markdown("""
        **灵犀** 是一个智能客服 Agent，支持：

        - 📦 订单查询
        - 🔄 退换货处理
        - ❓ 常见问题解答
        - 👤 转人工服务
        """)

        if st.button("清除对话"):
            st.session_state.messages = []
            st.session_state.session_id = f"streamlit-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            st.rerun()

        st.divider()
        st.caption(f"Session: {st.session_state.session_id}")

    # Initialize session
    init_session()

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("请输入您的问题..."):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get bot response
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    response = asyncio.run(send_message(prompt))
                    reply = response.get("reply", "抱歉，处理出现问题。")
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

                    # Show tool calls if any
                    tool_calls = response.get("tool_calls_made", [])
                    if tool_calls:
                        with st.expander("使用的工具"):
                            for tool in tool_calls:
                                st.code(tool)
                except Exception as e:
                    error_msg = f"连接失败: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})


if __name__ == "__main__":
    main()
