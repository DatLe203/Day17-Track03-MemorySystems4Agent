from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates, is_query_message
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Student TODO: implement Agent B / Advanced Agent.

    Required memory layers:
    1. within-session memory
    2. persistent `User.md`
    3. compact memory for long threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}
        self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: route between offline mode and live mode."""
        if self.langchain_agent and not self.force_offline:
            # Extract and update profile
            if not is_query_message(message):
                updates = extract_profile_updates(message)
                for k, v in updates.items():
                    self.profile_store.upsert_fact(user_id, k, v)

            # Append user message
            self.compact_memory.append(thread_id, "user", message)

            # Read profile & summary
            profile_text = self.profile_store.read_text(user_id)
            ctx = self.compact_memory.context(thread_id)
            summary_text = ctx.get("summary", "")
            active_messages = ctx.get("messages", [])

            # Estimate prompt tokens processed
            prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
            self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + prompt_tokens

            from langchain_core.messages import SystemMessage, AIMessage, HumanMessage

            system_content = f"Hồ sơ người dùng (User.md):\n{profile_text}\n\n"
            if summary_text:
                system_content += f"Tóm tắt hội thoại trước đó:\n{summary_text}\n\n"
            system_content += "Hãy trả lời người dùng dựa trên hồ sơ và lịch sử hội thoại."

            langchain_messages = [SystemMessage(content=system_content)]
            for m in active_messages[:-1]:
                if m["role"] == "user":
                    langchain_messages.append(HumanMessage(content=m["content"]))
                else:
                    langchain_messages.append(AIMessage(content=m["content"]))
            # Add current message
            langchain_messages.append(HumanMessage(content=message))

            try:
                response = self.langchain_agent.invoke(langchain_messages)
                reply_text = response.content
            except Exception:
                # Fallback to offline: pop user message from compact memory to avoid duplicates
                if active_messages:
                    active_messages.pop()
                return self._reply_offline(user_id, thread_id, message)

            # Append reply to compact memory
            self.compact_memory.append(thread_id, "assistant", reply_text)
            reply_tokens = estimate_tokens(reply_text)
            self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + reply_tokens

            return {
                "role": "assistant",
                "content": reply_text,
                "tokens": reply_tokens,
            }
        else:
            return self._reply_offline(user_id, thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement the deterministic advanced path.

        Pseudocode:
        1. Extract stable profile facts from the incoming message.
        2. Persist those facts into `User.md`.
        3. Append the message into compact memory.
        4. Estimate prompt-context load from `User.md` + summary + recent messages.
        5. Generate a response that can answer long-term recall questions.
        6. Append the assistant reply and update token counters.
        """
        # 1. Extract stable profile facts
        if not is_query_message(message):
            updates = extract_profile_updates(message)
            # 2. Persist those facts into User.md
            for k, v in updates.items():
                self.profile_store.upsert_fact(user_id, k, v)

        # 3. Append to compact memory
        self.compact_memory.append(thread_id, "user", message)

        # 4. Estimate prompt-context load
        prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
        self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + prompt_tokens

        # 5. Generate a response that can answer long-term recall questions
        reply_text = self._offline_response(user_id, thread_id, message)

        # 6. Append the assistant reply and update token counters
        self.compact_memory.append(thread_id, "assistant", reply_text)
        reply_tokens = estimate_tokens(reply_text)
        self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + reply_tokens

        return {
            "role": "assistant",
            "content": reply_text,
            "tokens": reply_tokens,
        }

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        """Student TODO: estimate the context carried into one turn.

        Hint:
        - Include `User.md`
        - Include compact summary text
        - Include recent kept messages
        """
        profile_text = self.profile_store.read_text(user_id)
        ctx = self.compact_memory.context(thread_id)
        summary_text = ctx.get("summary", "")
        active_messages_text = " ".join(msg["content"] for msg in ctx.get("messages", []))
        return estimate_tokens(profile_text) + estimate_tokens(summary_text) + estimate_tokens(active_messages_text)

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        """Student TODO: return a deterministic answer using persisted memory.

        Make sure the advanced agent can answer questions like:
        - "Mình tên gì?"
        - "Hiện tại mình làm nghề gì?"
        - "Nhắc lại style trả lời mình thích"
        - questions in the long stress dataset
        """
        profile = self.profile_store.get_profile_dict(user_id)

        # Check if it's a general description query
        is_general_query = any(q in message.lower() for q in ["ai không", "tóm tắt", "mô tả", "biết gì về"])

        answers = []
        if is_general_query:
            parts = []
            if profile["Tên"] != "Chưa rõ":
                parts.append(f"Tên: {profile['Tên']}")
            if profile["Nơi ở"] != "Chưa rõ":
                parts.append(f"Nơi ở: {profile['Nơi ở']}")
            if profile["Nghề nghiệp"] != "Chưa rõ":
                parts.append(f"Nghề nghiệp: {profile['Nghề nghiệp']}")
            if profile["Phong cách trả lời"] != "Chưa rõ":
                parts.append(f"Style: {profile['Phong cách trả lời']}")
            if profile["Đồ uống yêu thích"] != "Chưa rõ":
                parts.append(f"Đồ uống: {profile['Đồ uống yêu thích']}")
            if profile["Món ăn yêu thích"] != "Chưa rõ":
                parts.append(f"Món ăn: {profile['Món ăn yêu thích']}")
            if profile["Con vật nuôi"] != "Chưa rõ":
                parts.append(f"Thú cưng: {profile['Con vật nuôi']}")
            if profile["Sở thích / Mối quan tâm"] != "Chưa rõ":
                parts.append(f"Mối quan tâm: {profile['Sở thích / Mối quan tâm']}")
            return "Tôi có thông tin lưu trữ của bạn như sau: " + ", ".join(parts) + "."

        if "tên" in message.lower() and profile["Tên"] != "Chưa rõ":
            answers.append(f"Tên bạn là {profile['Tên']}.")
        if ("ở" in message.lower() or "đâu" in message.lower()) and profile["Nơi ở"] != "Chưa rõ":
            answers.append(f"Bạn đang ở {profile['Nơi ở']}.")
        if ("nghề" in message.lower() or "công việc" in message.lower() or "làm gì" in message.lower()) and profile["Nghề nghiệp"] != "Chưa rõ":
            answers.append(f"Nghề nghiệp hiện tại của bạn là {profile['Nghề nghiệp']}.")
        if ("style" in message.lower() or "phong cách" in message.lower() or "trả lời" in message.lower()) and profile["Phong cách trả lời"] != "Chưa rõ":
            answers.append(f"Phong cách trả lời bạn thích là {profile['Phong cách trả lời']}.")
        if ("đồ uống" in message.lower() or "uống" in message.lower()) and profile["Đồ uống yêu thích"] != "Chưa rõ":
            answers.append(f"Đồ uống yêu thích của bạn là {profile['Đồ uống yêu thích']}.")
        if ("món ăn" in message.lower() or "ăn gì" in message.lower()) and profile["Món ăn yêu thích"] != "Chưa rõ":
            answers.append(f"Món ăn yêu thích của bạn là {profile['Món ăn yêu thích']}.")
        if ("nuôi" in message.lower() or "con" in message.lower()) and profile["Con vật nuôi"] != "Chưa rõ":
            answers.append(f"Bạn nuôi con {profile['Con vật nuôi']}.")

        if answers:
            return " ".join(answers)
        return "Chào bạn, tôi chưa tìm thấy thông tin bạn yêu cầu trong hồ sơ."

    def _maybe_build_langchain_agent(self):
        """Student TODO: wire a live agent with tools and compact middleware.

        High-level design:
        - `build_chat_model(self.config.model)` for the selected provider
        - `InMemorySaver` for short-term thread state
        - tool to read `User.md`
        - tool to write/edit `User.md`
        - dynamic prompt that injects profile memory
        - summarization middleware for long threads
        """
        try:
            if self.config.model.api_key or self.config.model.provider == "ollama":
                self.langchain_agent = build_chat_model(self.config.model)
            else:
                self.langchain_agent = None
        except Exception:
            self.langchain_agent = None
