import sys
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# --- 1. 你的配置 (保持不变) ---
YOUR_API_KEY = "sk-aaf81618504c488fb69ee3d2a2391cfd"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

print("--- 正在使用 LangChain (OpenAI 兼容模式) 初始化 Qwen3-Max ---")

try:
    # --- 2. 初始化 ChatOpenAI ---
    # [关键修改 1] 明确启用 streaming
    chat = ChatOpenAI(
        model_name="qwen3-max",
        openai_api_key=YOUR_API_KEY,
        openai_api_base=BASE_URL,
        temperature=0.7,
        streaming=True,  # <-- 告诉 LangChain 我们打算使用流式
    )

    print("--- 模型初始化成功 ---")

    # --- 3. 初始化对话历史 (保持不变) ---
    chat_history = [
        SystemMessage(content="You are a helpful assistant. 你是一个博学多才的AI助手。"),
    ]

    print("\n--- 多轮对话已启动 (流式输出) ---")
    print("你可以开始提问了 (输入 'quit' 或 'q' 退出对话).")

    # --- 4. 聊天循环 ---
    while True:
        user_input = input("\n你: ")

        if user_input.lower() in ["quit", "q"]:
            print("感谢使用，再见！")
            break

        chat_history.append(HumanMessage(content=user_input))

        # --- [关键修改 2] 使用 .stream() 并处理数据块 ---

        print("\nQwen3-Max (流式...): ")

        # 4.1 创建一个空字符串，用于累积完整的回复
        full_response_content = ""

        try:
            # 4.2 调用 .stream()，它返回一个数据块 (chunk) 迭代器
            for chunk in chat.stream(chat_history):
                # 4.3 检查数据块中是否有内容
                # (chunk.content 通常是字符串，有时可能为 None)
                if chunk.content:
                    # 4.4 立即将数据块内容打印到终端
                    # end="" 防止 print 自动换行
                    # flush=True 确保内容立即显示
                    print(chunk.content, end="", flush=True)

                    # 4.5 将数据块累积到完整回复中
                    full_response_content += chunk.content

            # 4.6 (重要) 在流式结束后，打印一个换行符，使下次 "你: " 的提示在新行开始
            print()

            # 4.7 (重要) 将 *完整的* 回复封装为 AIMessage 并添加到历史记录中
            # 这样，下一次调用时，AI 才能 "记住" 它这次的完整回复
            chat_history.append(AIMessage(content=full_response_content))

        except Exception as e:
            print(f"调用模型时出错: {e}")
            # 如果出错，从历史记录中移除刚刚添加的用户消息
            chat_history.pop()


except Exception as e:
    print(f"--- 发生初始化错误 ---")
    print(f"错误详情: {e}")
    print("请检查：\n1. 你的 API Key 是否正确。\n2. BASE_URL 是否正确。")