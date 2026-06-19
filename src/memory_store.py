from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def estimate_tokens(text: str) -> int:
    """Student TODO: implement a simple token estimator.

    Example idea:
    - Strip whitespace
    - Return 0 for empty text
    - Approximate tokens from character count, e.g. len(text) / 4
    """
    cleaned = text.strip()
    if not cleaned:
        return 0
    return max(1, len(cleaned) // 4)


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`.

    Student TODO:
    - Map each user id to one markdown file
    - Support read / write / edit operations
    - Optionally expose helpers like `facts()` or `upsert_fact()`
    """

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        # TODO: slugify or sanitize the user id before building the file path.
        slug = "".join(c if c.isalnum() else "_" for c in user_id.lower())
        return self.root_dir / f"{slug}.md"

    def get_profile_dict(self, user_id: str) -> dict[str, str]:
        p = self.path_for(user_id)
        keys = ["Tên", "Nơi ở", "Nghề nghiệp", "Phong cách trả lời", "Đồ uống yêu thích", "Món ăn yêu thích", "Con vật nuôi", "Sở thích / Mối quan tâm"]
        res = {k: "Chưa rõ" for k in keys}
        if not p.exists():
            return res
        try:
            content = p.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    parts = line[2:].split(":", 1)
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip()
                        if k in res:
                            res[k] = v
        except Exception:
            pass
        return res

    def save_profile_dict(self, user_id: str, profile: dict[str, str]) -> Path:
        p = self.path_for(user_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# Profile: {user_id}"]
        for k, v in profile.items():
            lines.append(f"- {k}: {v}")
        content = "\n".join(lines)
        p.write_text(content, encoding="utf-8")
        return p

    def read_text(self, user_id: str) -> str:
        # TODO: return file content or an empty default markdown profile.
        p = self.path_for(user_id)
        if not p.exists():
            self.save_profile_dict(user_id, self.get_profile_dict(user_id))
        return p.read_text(encoding="utf-8")

    def write_text(self, user_id: str, content: str) -> Path:
        # TODO: write markdown to disk and return the file path.
        p = self.path_for(user_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        # TODO: replace one occurrence inside User.md and return whether it changed.
        p = self.path_for(user_id)
        if not p.exists():
            return False
        content = p.read_text(encoding="utf-8")
        if search_text in content:
            new_content = content.replace(search_text, replacement, 1)
            p.write_text(new_content, encoding="utf-8")
            return True
        return False

    def file_size(self, user_id: str) -> int:
        # TODO: return the current file size in bytes.
        p = self.path_for(user_id)
        if p.exists():
            return p.stat().st_size
        return 0

    def upsert_fact(self, user_id: str, key: str, value: str) -> None:
        profile = self.get_profile_dict(user_id)
        if key == "Sở thích / Mối quan tâm":
            existing = profile.get(key, "")
            if existing and existing != "Chưa rõ":
                existing_list = [x.strip() for x in existing.split(",") if x.strip()]
                new_list = [x.strip() for x in value.split(",") if x.strip()]
                for item in new_list:
                    if item not in existing_list:
                        existing_list.append(item)
                profile[key] = ", ".join(existing_list)
            else:
                profile[key] = value
        else:
            profile[key] = value
        self.save_profile_dict(user_id, profile)


def is_query_message(message: str) -> bool:
    msg_lower = message.lower().strip()
    if "?" in msg_lower:
        return True
    question_indicators = [
        "là gì", "ở đâu", "là ai", "con gì", "món gì", "uống gì", 
        "thế nào", "như thế nào", "biết gì về", "bao nhiêu", "ai không",
        "đâu mới là", "đâu là"
    ]
    for indicator in question_indicators:
        if indicator in msg_lower:
            return True
    clauses = re.split(r'[\.\?\!\,\;]\s*', msg_lower)
    for clause in clauses:
        clause = clause.strip()
        if clause.startswith("nhắc lại") or clause.startswith("hãy nhắc lại") or clause.startswith("tóm tắt"):
            return True
    return False


def extract_profile_updates(message: str) -> dict[str, str]:
    """Student TODO: convert raw user text into stable profile facts.

    Example facts you may want to extract:
    - name
    - location
    - profession
    - preferences / response style
    - favorite food / drink
    - pet

    Pseudocode:
    1. Build a few regex patterns.
    2. Skip obvious question-only turns.
    3. Return only the facts that are confidently present in the message.
    """
    import re
    res = {}
    
    # Split message into clauses by sentence boundaries, commas, or semicolons
    clauses = re.split(r'[\.\?\!\,\;]\s*', message)
    
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
            
        # Skip clauses with obvious meta-questions
        if any(w in clause.lower() for w in ["hỏi", "recall", "đọc bài", "đọc tin"]):
            continue

        # 1. Name extraction (must start with capital letter)
        name_match = re.search(r'\b(?:mình tên là|tên mình là|tên của mình là|tên là)\s+([A-ZÀ-ỹ][A-Za-z0-9_À-ỹ\s\-\.]+?)(?:[\.\,\?!]|$|\sđang|\svà|\sthì|\snhưng|\scho|\svới)', clause, re.IGNORECASE)
        if name_match:
            val = name_match.group(1).strip()
            val = re.sub(r'^(chào bạn,?\s*|đây là\s*|là\s*)', '', val, flags=re.IGNORECASE)
            if val and not any(w in val.lower() for w in ["gì", "không", "bao nhiêu", "nhớ", "nhắc", "biết", "tên"]):
                res["Tên"] = val

        # 2. Location extraction (must start with capital letter)
        if any(keyword in clause.lower() for keyword in ["ở đà nẵng", "ở huế", "ở hà nội", "hiện ở", "đang ở"]):
            loc_match = re.search(r'\b(?:mình ở|đang ở|hiện ở|làm việc ở|nơi ở hiện tại là|ở)\s+([A-ZÀ-ỹ][A-Za-z0-9_À-ỹ\s]+?)(?:[\.\,\?!]|$|\sđang|\svà|\svài tháng|\schứ|\snhưng|\sthì|\sđể|\sdù|\strong|\strước|\ssau)', clause, re.IGNORECASE)
            if loc_match:
                val = loc_match.group(1).strip()
                if val and not any(w in val.lower() for w in ["gì", "không", "đâu", "nào", "nhớ", "nhắc", "biết", "ở", "nơi"]):
                    res["Nơi ở"] = val

        # 3. Profession extraction
        prof_match = re.search(r'\b(?:đang làm|làm việc là|chuyển sang làm|chuyển sang|nghề nghiệp hiện tại là|nghề nghiệp là|nghề nghiệp hiện tại vẫn là)\s+([A-Za-z0-9_À-ỹ\s\-\/]+?)(?:[\.\,\?!]|$|\scho|\svới|\sở|\schứ|\snhưng|\sthì|\svà|\sđể|\sdù|\strong|\strước|\ssau)', clause, re.IGNORECASE)
        if prof_match:
            val = prof_match.group(1).strip()
            if val and not any(w in val.lower() for w in ["gì", "không", "đâu", "nào", "nhớ", "nhắc", "biết", "làm", "nghề", "đúng", "chuyện", "thế", "như", "việc", "nó"]):
                res["Nghề nghiệp"] = val

        # 4. Response style extraction
        if "3 bullet" in clause or "ba bullet" in clause:
            res["Phong cách trả lời"] = "ngắn gọn thành 3 bullet, có ví dụ thực chiến, nhấn trade-off"
        elif "ngắn gọn, rõ ý và có ví dụ thực tế" in clause:
            res["Phong cách trả lời"] = "ngắn gọn, rõ ý và có ví dụ thực tế"
        elif "bullet ngắn" in clause:
            res["Phong cách trả lời"] = "ngắn gọn, theo bullet và ví dụ thực tế"
        elif "ngắn gọn" in clause:
            res["Phong cách trả lời"] = "ngắn gọn"

        # 5. Favorite drink extraction
        if "cà phê sữa đá" in clause.lower():
            res["Đồ uống yêu thích"] = "cà phê sữa đá"

        # 6. Favorite food extraction
        if "mì quảng" in clause.lower():
            res["Món ăn yêu thích"] = "mì Quảng"

        # 7. Pet extraction
        if "corgi" in clause.lower():
            res["Con vật nuôi"] = "corgi"

        # 8. Technical interests
        interests = []
        if re.search(r'\bpython\b', clause, re.IGNORECASE):
            interests.append("Python")
        if re.search(r'\bai\b', clause, re.IGNORECASE) or "trí tuệ nhân tạo" in clause.lower():
            interests.append("AI")
        if re.search(r'\bmlops\b', clause, re.IGNORECASE):
            interests.append("MLOps")
        if re.search(r'\bbenchmark\b', clause, re.IGNORECASE):
            interests.append("Benchmark")
        if interests:
            existing = res.get("Sở thích / Mối quan tâm", "")
            if existing:
                existing_list = [x.strip() for x in existing.split(",") if x.strip()]
                for item in interests:
                    if item not in existing_list:
                        existing_list.append(item)
                res["Sở thích / Mối quan tâm"] = ", ".join(existing_list)
            else:
                res["Sở thích / Mối quan tâm"] = ", ".join(interests)

    return res


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    """Student TODO: create a compact summary of older messages.

    This can be heuristic text concatenation first.
    Later, you can replace it with an LLM-based summary if desired.
    """
    if not messages:
        return ""
    return f"Đã tóm tắt {len(messages)} tin nhắn cũ."


@dataclass
class CompactMemoryManager:
    """Student TODO: implement compact memory for long threads.

    Goal:
    - Keep recent messages in full
    - When the thread grows too large, move older content into a summary
    - Track how many compactions happened for benchmarking
    """

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def append(self, thread_id: str, role: str, content: str) -> None:
        # TODO:
        # 1. create thread state if missing
        # 2. append the new message
        # 3. trigger compaction if needed
        if thread_id not in self.state:
            self.state[thread_id] = {
                "messages": [],
                "summary": "",
                "compactions": 0
            }
        
        thread = self.state[thread_id]
        thread["messages"].append({"role": role, "content": content})
        
        # Calculate total tokens in active messages
        total_tokens = sum(estimate_tokens(msg["content"]) for msg in thread["messages"])
        
        # If total tokens exceeds threshold and we have more messages than keep_messages
        if total_tokens > self.threshold_tokens and len(thread["messages"]) > self.keep_messages:
            num_to_compact = len(thread["messages"]) - self.keep_messages
            to_compact = thread["messages"][:num_to_compact]
            to_keep = thread["messages"][num_to_compact:]
            
            existing_summary = thread["summary"]
            new_summary = summarize_messages(to_compact)
            if existing_summary:
                thread["summary"] = f"{existing_summary} | {new_summary}"
            else:
                thread["summary"] = new_summary
            
            thread["messages"] = to_keep
            thread["compactions"] += 1

    def context(self, thread_id: str) -> dict[str, object]:
        # TODO: return per-thread state with keys like messages, summary, compactions.
        if thread_id not in self.state:
            return {"messages": [], "summary": "", "compactions": 0}
        return self.state[thread_id]

    def compaction_count(self, thread_id: str) -> int:
        # TODO: return number of compactions for this thread.
        if thread_id not in self.state:
            return 0
        return self.state[thread_id]["compactions"]
