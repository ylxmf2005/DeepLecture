import os

import pytest

from deeplecture.llm.llm_factory import LLMFactory, ModelRegistry


@pytest.mark.skipif(
    not os.getenv("RUN_GEMINI_LIVE"),
    reason="Set RUN_GEMINI_LIVE=1 to run the live Gemini smoke test.",
)
def test_gemini_pro_can_reply() -> None:
    """Smoke test for the gemini-2.5-pro config using the real LLM pipeline."""
    registry = ModelRegistry()
    cfg = registry.get_model_config("gemini-2.5-pro")

    # Ensure we resolved the intended model instead of falling back to default.
    assert cfg["provider"] == "gemini"
    assert cfg["model"] == "gemini-2.5-pro"
    assert cfg["base_url"].startswith("http")

    llm = LLMFactory(registry=registry).get_llm(model_name="gemini-2.5-pro")

    prompt = "Answer in one sentence: what is 2 + 2? Output only the number."
    reply = llm.generate_response(prompt)

    assert isinstance(reply, str)
    # Gemini tends to return '4' or '4\n'; accept any non-empty string containing 4.
    assert "4" in reply
