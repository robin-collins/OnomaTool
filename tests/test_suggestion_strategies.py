"""Tests for SuggestionStrategy pattern (§12)."""

from onomatool.models import ProcessingResult
from onomatool.suggestion_strategy import (
    MultiPassStrategy,
    TextOnlyStrategy,
    select_strategy,
)


def test_select_strategy_text_only():
    """TC-SS-001: No image paths selects TextOnlyStrategy."""
    strategy = select_strategy([])
    assert isinstance(strategy, TextOnlyStrategy)


def test_select_strategy_with_images():
    """TC-SS-002: Image paths selects MultiPassStrategy."""
    strategy = select_strategy(["/tmp/img.png"])
    assert isinstance(strategy, MultiPassStrategy)


def test_text_only_strategy_calls_get_suggestions():
    """TC-SS-003: TextOnlyStrategy makes one call with markdown content."""
    config = {"default_provider": "mock", "naming_convention": "snake_case"}
    result = ProcessingResult(
        markdown="test content", source_path="test.txt", file_type="txt"
    )

    strategy = TextOnlyStrategy()
    suggestions = strategy.get_suggestions(result, "test.txt", [], config)
    assert suggestions is not None
    assert len(suggestions) == 3
    assert suggestions[0] == "mock_file_one"


def test_multi_pass_strategy_with_mock(tmp_path):
    """TC-SS-004: MultiPassStrategy works with mock provider (makes multiple calls)."""
    config = {"default_provider": "mock", "naming_convention": "snake_case"}
    # Create a real image file so encode_image_base64 works
    img_file = tmp_path / "test_img.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    result = ProcessingResult(
        markdown="test content",
        images=[str(img_file)],
        source_path="test.pdf",
        file_type="pdf",
    )

    strategy = MultiPassStrategy()
    suggestions = strategy.get_suggestions(result, "test.pdf", [str(img_file)], config)
    assert suggestions is not None
    assert len(suggestions) == 3


def test_text_only_strategy_camel_case():
    """TC-SS-005: TextOnlyStrategy respects naming convention."""
    config = {"default_provider": "mock", "naming_convention": "camelCase"}
    result = ProcessingResult(markdown="test", source_path="test.txt", file_type="txt")

    strategy = TextOnlyStrategy()
    suggestions = strategy.get_suggestions(result, "test.txt", [], config)
    assert suggestions[0] == "mockFileOne"
