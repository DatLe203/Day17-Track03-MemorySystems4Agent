from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Student TODO: read JSON conversations from disk."""
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def recall_points(answer: str, expected: list[str]) -> float:
    """Student TODO: return 0 / 0.5 / 1 depending on how many expected facts appear."""
    if not expected:
        return 1.0
    ans_lower = answer.lower()
    matches = 0
    for fact in expected:
        if fact.lower() in ans_lower:
            matches += 1
    return matches / len(expected)


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Student TODO: add a lightweight quality score for offline mode."""
    recall = recall_points(answer, expected)
    if "không biết" in answer.lower() or "chưa cung cấp" in answer.lower() or "chưa tìm thấy" in answer.lower():
        return 0.1
    # Base score on recall with small formatting check
    score = 0.5 + 0.5 * recall
    if len(answer) > 300:
        score -= 0.1
    return max(0.1, min(1.0, score))


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    """Student TODO: evaluate one agent over many conversations.

    Pseudocode:
    1. Feed all turns to the agent.
    2. Track `agent tokens only`.
    3. Track `prompt tokens processed`.
    4. Ask recall questions in a fresh thread.
    5. Compute average recall and quality.
    6. Record memory file growth and compaction count.
    """
    import shutil
    import os
    
    profiles_dir = config.state_dir / "profiles"
    if profiles_dir.exists():
        shutil.rmtree(profiles_dir)
    profiles_dir.mkdir(parents=True, exist_ok=True)
    
    # Reset agent session/memory states
    if hasattr(agent, "sessions"):
        agent.sessions = {}
    if hasattr(agent, "compact_memory"):
        agent.compact_memory.state = {}
    if hasattr(agent, "thread_tokens"):
        agent.thread_tokens = {}
    if hasattr(agent, "thread_prompt_tokens"):
        agent.thread_prompt_tokens = {}
        
    total_agent_tokens = 0
    total_prompt_tokens = 0
    total_compactions = 0
    
    recall_scores = []
    quality_scores = []
    
    for conv in conversations:
        user_id = conv["user_id"]
        conv_id = conv["id"]
        thread_id = f"{conv_id}-thread"
        
        # Feed all turns of the conversation
        for turn in conv["turns"]:
            res = agent.reply(user_id, thread_id, turn)
            total_agent_tokens += res.get("tokens", 0)
            
        # Accumulate prompt tokens and compaction counts for the main thread
        total_prompt_tokens += agent.prompt_token_usage(thread_id)
        total_compactions += agent.compaction_count(thread_id)
        
        # Run recall questions in fresh threads
        for i, q_item in enumerate(conv.get("recall_questions", [])):
            question = q_item["question"]
            expected = q_item["expected_contains"]
            
            recall_thread_id = f"{conv_id}-recall-{i}"
            res_recall = agent.reply(user_id, recall_thread_id, question)
            
            # Accumulate recall turn tokens
            total_agent_tokens += res_recall.get("tokens", 0)
            total_prompt_tokens += agent.prompt_token_usage(recall_thread_id)
            
            score = recall_points(res_recall["content"], expected)
            qual = heuristic_quality(res_recall["content"], expected)
            
            if agent_name == "Advanced Agent":
                print(f"[RECALL DEBUG] Q: {question} | Expected: {expected} | Actual: {res_recall['content']} | Score: {score}")
            
            recall_scores.append(score)
            quality_scores.append(qual)
            
    # Calculate memory growth
    total_mem_size = 0
    if profiles_dir.exists():
        for f in profiles_dir.iterdir():
            if f.is_file():
                total_mem_size += f.stat().st_size
                
    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    
    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=total_agent_tokens,
        prompt_tokens_processed=total_prompt_tokens,
        recall_score=avg_recall,
        response_quality=avg_quality,
        memory_growth_bytes=total_mem_size,
        compactions=total_compactions
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Student TODO: print a markdown table or tabulated output."""
    from tabulate import tabulate
    table_data = []
    for r in rows:
        table_data.append([
            r.agent_name,
            r.agent_tokens_only,
            r.prompt_tokens_processed,
            f"{r.recall_score:.2%}",
            f"{r.response_quality:.2%}",
            f"{r.memory_growth_bytes} B",
            r.compactions
        ])
    headers = [
        "Agent",
        "Agent Tokens Only",
        "Prompt Tokens Processed",
        "Cross-session Recall",
        "Response Quality",
        "Memory Growth (bytes)",
        "Compactions"
    ]
    return tabulate(table_data, headers=headers, tablefmt="github")


def main() -> None:
    """Student TODO: run both benchmark suites.

    Required benchmark sections:
    - Standard benchmark from `data/conversations.json`
    - Long-context stress benchmark from `data/advanced_long_context.json`

    Compare:
    - Baseline
    - Advanced

    Keep the same output columns as the solved lab:
    - Agent tokens only
    - Prompt tokens processed
    - Cross-session recall
    - Response quality
    - Memory growth (bytes)
    - Compactions
    """
    config = load_config(Path(__file__).resolve().parent.parent)
    
    data_dir = config.base_dir / "data"
    std_convs = load_conversations(data_dir / "conversations.json")
    stress_convs = load_conversations(data_dir / "advanced_long_context.json")
    
    baseline_agent = BaselineAgent(config, force_offline=True)
    advanced_agent = AdvancedAgent(config, force_offline=True)
    
    print("=== RUNNING STANDARD BENCHMARK ===")
    baseline_row_std = run_agent_benchmark("Baseline Agent", baseline_agent, std_convs, config)
    advanced_row_std = run_agent_benchmark("Advanced Agent", advanced_agent, std_convs, config)
    print(format_rows([baseline_row_std, advanced_row_std]))
    print("\n")
    
    print("=== RUNNING LONG-CONTEXT STRESS BENCHMARK ===")
    baseline_row_str = run_agent_benchmark("Baseline Agent", baseline_agent, stress_convs, config)
    advanced_row_str = run_agent_benchmark("Advanced Agent", advanced_agent, stress_convs, config)
    print(format_rows([baseline_row_str, advanced_row_str]))
    print("\n")


if __name__ == "__main__":
    main()
