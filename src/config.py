from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from model_provider import ProviderConfig


@dataclass
class LabConfig:
    """Student TODO: define the shared configuration for the lab.

    Hints:
    - Keep paths for the repo root, dataset directory, and state directory.
    - Add compact-memory settings such as threshold and number of messages to keep.
    - Add provider settings for `openai`, `custom`, `gemini`, `anthropic`, `ollama`, and `openrouter`.
    """

    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig


def load_config(base_dir: Path | None = None) -> LabConfig:
    """Student TODO: load environment variables and return a LabConfig.

    Pseudocode:
    1. Resolve the repo root or default to the current file parent.
    2. Optionally load values from `.env`.
    3. Create `state/` if it does not exist.
    4. Return a populated LabConfig instance.
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()

    # Create state and profile directories
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "profiles").mkdir(parents=True, exist_ok=True)

    # Load provider parameters
    provider = os.environ.get("LLM_PROVIDER", "openai")
    
    # Sensible defaults based on provider
    default_model = "gpt-4o-mini"
    if provider == "gemini":
        default_model = "gemini-1.5-flash"
    elif provider == "ollama":
        default_model = "llama3"
    elif provider == "anthropic":
        default_model = "claude-3-5-sonnet-20240620"
    
    model_name = os.environ.get("LLM_MODEL", default_model)
    
    # Handle api keys
    api_key = None
    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    elif provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
    else:
        api_key = os.environ.get("LLM_API_KEY")

    base_url = os.environ.get("LLM_BASE_URL")
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.0"))

    model_config = ProviderConfig(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url
    )

    # Judge model config
    judge_provider = os.environ.get("JUDGE_PROVIDER", provider)
    
    default_judge_model = "gpt-4o-mini"
    if judge_provider == "gemini":
        default_judge_model = "gemini-1.5-flash"
    elif judge_provider == "ollama":
        default_judge_model = "llama3"
    elif judge_provider == "anthropic":
        default_judge_model = "claude-3-5-sonnet-20240620"
        
    judge_model_name = os.environ.get("JUDGE_MODEL", default_judge_model)
    
    judge_api_key = None
    if judge_provider == "openai":
        judge_api_key = os.environ.get("OPENAI_API_KEY")
    elif judge_provider == "gemini":
        judge_api_key = os.environ.get("GEMINI_API_KEY")
    elif judge_provider == "anthropic":
        judge_api_key = os.environ.get("ANTHROPIC_API_KEY")
    elif judge_provider == "openrouter":
        judge_api_key = os.environ.get("OPENROUTER_API_KEY")
    else:
        judge_api_key = os.environ.get("JUDGE_API_KEY") or api_key

    judge_base_url = os.environ.get("JUDGE_BASE_URL")
    judge_temp = float(os.environ.get("JUDGE_TEMPERATURE", "0.0"))

    judge_config = ProviderConfig(
        provider=judge_provider,
        model_name=judge_model_name,
        temperature=judge_temp,
        api_key=judge_api_key,
        base_url=judge_base_url
    )

    # Compact memory configs
    threshold = int(os.environ.get("COMPACT_THRESHOLD_TOKENS", "800"))
    keep_messages = int(os.environ.get("COMPACT_KEEP_MESSAGES", "4"))

    return LabConfig(
        base_dir=root,
        data_dir=root / "data",
        state_dir=state_dir,
        compact_threshold_tokens=threshold,
        compact_keep_messages=keep_messages,
        model=model_config,
        judge_model=judge_config,
    )
