from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Student TODO: implement Agent A.

    Requirements:
    - Within-session memory only
    - No persistent `User.md`
    - Should forget long-term facts across new threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: return the agent response and token accounting.

        Pseudocode:
        - If a live agent exists, call the live path.
        - Otherwise use a deterministic offline path.
        """
        if self.langchain_agent and not self.force_offline:
            if thread_id not in self.sessions:
                self.sessions[thread_id] = SessionState()
            session = self.sessions[thread_id]
            
            session.messages.append({"role": "user", "content": message})
            
            # Estimate prompt tokens processed so far
            prompt_text = " ".join(m["content"] for m in session.messages)
            prompt_tokens = estimate_tokens(prompt_text)
            session.prompt_tokens_processed += prompt_tokens
            
            from langchain_core.messages import AIMessage, HumanMessage
            langchain_messages = []
            for m in session.messages[:-1]:
                if m["role"] == "user":
                    langchain_messages.append(HumanMessage(content=m["content"]))
                else:
                    langchain_messages.append(AIMessage(content=m["content"]))
            # Add the current message
            langchain_messages.append(HumanMessage(content=message))
            
            try:
                response = self.langchain_agent.invoke(langchain_messages)
                reply_text = response.content
            except Exception:
                # Fallback to offline
                session.messages.pop()  # remove user message to avoid duplicate addition in offline
                return self._reply_offline(thread_id, message)
                
            session.messages.append({"role": "assistant", "content": reply_text})
            reply_tokens = estimate_tokens(reply_text)
            session.token_usage += reply_tokens
            
            return {
                "role": "assistant",
                "content": reply_text,
                "tokens": reply_tokens,
            }
        else:
            return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        # TODO: return cumulative agent token count for one thread.
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].token_usage

    def prompt_token_usage(self, thread_id: str) -> int:
        # TODO: estimate how much prompt context this baseline kept processing.
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].prompt_tokens_processed

    def compaction_count(self, thread_id: str) -> int:
        # Baseline has no compact memory.
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement a simple offline behavior.

        Suggested behavior:
        - Store the new user message in the session
        - Generate a short deterministic reply
        - Update token counts
        - Never remember facts across different thread ids
        """
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()
        session = self.sessions[thread_id]
        
        session.messages.append({"role": "user", "content": message})
        
        # Estimate prompt context tokens (input context includes all messages so far, including current message)
        prompt_tokens = sum(estimate_tokens(msg["content"]) for msg in session.messages)
        session.prompt_tokens_processed += prompt_tokens
        
        # Build deterministic reply
        reply_text = "Chào bạn, tôi đã nhận được thông tin."
        
        # Simple keyword-based question responder for baseline (within active session only)
        is_question = any(q in message.lower() for q in ["tên", "ở đâu", "nghề", "style", "phong cách", "đồ uống", "món ăn", "nuôi", "con gì"])
        if is_question:
            past_messages_text = " ".join(msg["content"] for msg in session.messages[:-1])
            extracted = extract_profile_updates(past_messages_text)
            
            answers = []
            if "tên" in message.lower() and "Tên" in extracted:
                answers.append(f"Tên bạn là {extracted['Tên']}.")
            if ("ở" in message.lower() or "đâu" in message.lower()) and "Nơi ở" in extracted:
                answers.append(f"Bạn ở {extracted['Nơi ở']}.")
            if ("nghề" in message.lower() or "công việc" in message.lower() or "làm gì" in message.lower()) and "Nghề nghiệp" in extracted:
                answers.append(f"Nghề nghiệp của bạn là {extracted['Nghề nghiệp']}.")
            if "style" in message.lower() or "phong cách" in message.lower() or "trả lời" in message.lower():
                if "Phong cách trả lời" in extracted:
                    answers.append(f"Style trả lời bạn thích là {extracted['Phong cách trả lời']}.")
            if "đồ uống" in message.lower() or "uống" in message.lower():
                if "Đồ uống yêu thích" in extracted:
                    answers.append(f"Đồ uống yêu thích của bạn là {extracted['Đồ uống yêu thích']}.")
            if "món ăn" in message.lower() or "ăn gì" in message.lower():
                if "Món ăn yêu thích" in extracted:
                    answers.append(f"Món ăn yêu thích của bạn là {extracted['Món ăn yêu thích']}.")
            if "nuôi" in message.lower() or "con" in message.lower():
                if "Con vật nuôi" in extracted:
                    answers.append(f"Bạn nuôi con {extracted['Con vật nuôi']}.")
            
            if answers:
                reply_text = " ".join(answers)
            else:
                reply_text = "Tôi không biết thông tin này vì bạn chưa cung cấp trong phiên trò chuyện hiện tại."

        session.messages.append({"role": "assistant", "content": reply_text})
        reply_tokens = estimate_tokens(reply_text)
        session.token_usage += reply_tokens

        return {
            "role": "assistant",
            "content": reply_text,
            "tokens": reply_tokens,
        }

    def _maybe_build_langchain_agent(self):
        """Student TODO: optionally wire `create_agent` + `InMemorySaver` here.

        Use `build_chat_model(self.config.model)` so the baseline can run with any supported provider.
        """
        try:
            if self.config.model.api_key or self.config.model.provider == "ollama":
                self.langchain_agent = build_chat_model(self.config.model)
            else:
                self.langchain_agent = None
        except Exception:
            self.langchain_agent = None
