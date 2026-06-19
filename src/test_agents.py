from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


def make_config(tmp_path: Path):
    """Student TODO: build an isolated config for tests."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "profiles").mkdir(parents=True, exist_ok=True)
    
    from config import LabConfig
    from model_provider import ProviderConfig
    
    model_config = ProviderConfig(
        provider="openai",
        model_name="gpt-4o-mini",
        temperature=0.0
    )
    
    return LabConfig(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_dir=state_dir,
        compact_threshold_tokens=50,
        compact_keep_messages=2,
        model=model_config,
        judge_model=model_config
    )


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    """Student TODO: verify `User.md` can be created, updated, and edited."""
    from memory_store import UserProfileStore
    profiles_dir = tmp_path / "state" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    store = UserProfileStore(profiles_dir)
    
    user_id = "test_user"
    
    # 1. read_text should initialize default template
    content = store.read_text(user_id)
    assert "Profile: test_user" in content
    assert "Tên: Chưa rõ" in content
    
    # 2. write_text
    custom_content = "# Profile: test_user\n- Tên: John Doe\n- Nơi ở: Hanoi"
    p = store.write_text(user_id, custom_content)
    assert p.exists()
    assert store.read_text(user_id) == custom_content
    
    # 3. edit_text
    edited = store.edit_text(user_id, "John Doe", "Jane Doe")
    assert edited is True
    assert "Jane Doe" in store.read_text(user_id)
    assert "John Doe" not in store.read_text(user_id)
    
    # 4. file_size
    assert store.file_size(user_id) > 0


def test_compact_trigger(tmp_path: Path) -> None:
    """Student TODO: verify long threads trigger compaction."""
    from memory_store import CompactMemoryManager
    manager = CompactMemoryManager(threshold_tokens=50, keep_messages=2)
    thread_id = "thread-1"
    
    manager.append(thread_id, "user", "Hello first message.")
    manager.append(thread_id, "assistant", "Hello first reply.")
    
    assert manager.compaction_count(thread_id) == 0
    
    # Send a long message to exceed the 50 token threshold
    large_msg = "This is a very long message designed to trigger compaction. It should contain more than 200 characters so that the token estimator counts more than 50 tokens for this message alone, prompting the compact memory manager to compress old messages."
    manager.append(thread_id, "user", large_msg)
    
    assert manager.compaction_count(thread_id) == 1
    ctx = manager.context(thread_id)
    assert len(ctx["messages"]) == 2
    assert ctx["summary"] != ""


def test_cross_session_recall(tmp_path: Path) -> None:
    """Student TODO: verify advanced remembers across sessions and baseline does not."""
    config = make_config(tmp_path)
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)
    
    user_id = "dungct"
    thread1 = "thread-first"
    thread2 = "thread-second"
    
    intro = "Chào bạn, mình tên là DũngCT và mình thích uống cà phê sữa đá."
    
    # Session 1: Feed intro
    baseline.reply(user_id, thread1, intro)
    advanced.reply(user_id, thread1, intro)
    
    # Session 2: Ask recall in a new thread
    question = "Tên mình là gì và mình thích uống gì?"
    
    res_baseline = baseline.reply(user_id, thread2, question)
    res_advanced = advanced.reply(user_id, thread2, question)
    
    # Baseline agent should NOT remember
    assert "dũngct" not in res_baseline["content"].lower()
    
    # Advanced agent SHOULD remember
    assert "dũngct" in res_advanced["content"].lower()
    assert "cà phê sữa đá" in res_advanced["content"].lower()


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    """Student TODO: compare prompt load of baseline vs advanced on a long thread."""
    config = make_config(tmp_path)
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)
    
    user_id = "dungct"
    thread_id = "long-thread"
    
    # Send 10 messages of moderate length (approx 15 tokens each)
    for i in range(10):
        msg = f"Tin nhắn thứ {i} trong cuộc đối thoại rất dài này, nhằm mục đích kiểm tra nén bộ nhớ."
        baseline.reply(user_id, thread_id, msg)
        advanced.reply(user_id, thread_id, msg)
        
    base_prompt_tokens = baseline.prompt_token_usage(thread_id)
    adv_prompt_tokens = advanced.prompt_token_usage(thread_id)
    
    assert advanced.compaction_count(thread_id) > 0
    assert adv_prompt_tokens < base_prompt_tokens
