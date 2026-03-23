"""Tests for Pydantic filename suggestion models (§4)."""

import pytest
from pydantic import ValidationError

from onomatool.models import (
    CamelCaseFilenameSuggestions,
    DotNotationFilenameSuggestions,
    FilenameSuggestions,
    KebabCaseFilenameSuggestions,
    NaturalLanguageFilenameSuggestions,
    PascalCaseFilenameSuggestions,
    SnakeCaseFilenameSuggestions,
    generate_json_schema_from_model,
    get_model_for_naming_convention,
)


# TC-MOD-001: snake_case valid
def test_snake_case_valid():
    m = SnakeCaseFilenameSuggestions(
        suggestions=["hello_world", "foo_bar", "test_file"]
    )
    assert len(m.suggestions) == 3


# TC-MOD-002: snake_case invalid
def test_snake_case_invalid():
    with pytest.raises(ValidationError):
        SnakeCaseFilenameSuggestions(suggestions=["HelloWorld", "foo_bar", "test_file"])


# TC-MOD-003: camelCase valid
def test_camel_case_valid():
    m = CamelCaseFilenameSuggestions(suggestions=["helloWorld", "fooBar", "testFile"])
    assert len(m.suggestions) == 3


# TC-MOD-004: camelCase invalid
def test_camel_case_invalid():
    with pytest.raises(ValidationError):
        CamelCaseFilenameSuggestions(suggestions=["hello_world", "fooBar", "testFile"])


# TC-MOD-005: kebab-case valid
def test_kebab_case_valid():
    m = KebabCaseFilenameSuggestions(
        suggestions=["hello-world", "foo-bar", "test-file"]
    )
    assert len(m.suggestions) == 3


# TC-MOD-006: kebab-case invalid
def test_kebab_case_invalid():
    with pytest.raises(ValidationError):
        KebabCaseFilenameSuggestions(
            suggestions=["hello_world", "foo-bar", "test-file"]
        )


# TC-MOD-007: PascalCase valid
def test_pascal_case_valid():
    m = PascalCaseFilenameSuggestions(suggestions=["HelloWorld", "FooBar", "TestFile"])
    assert len(m.suggestions) == 3


# TC-MOD-008: PascalCase invalid
def test_pascal_case_invalid():
    with pytest.raises(ValidationError):
        PascalCaseFilenameSuggestions(suggestions=["helloWorld", "FooBar", "TestFile"])


# TC-MOD-009: dot.notation valid
def test_dot_notation_valid():
    m = DotNotationFilenameSuggestions(
        suggestions=["hello.world", "foo.bar", "test.file"]
    )
    assert len(m.suggestions) == 3


# TC-MOD-010: natural language valid
def test_natural_language_valid():
    m = NaturalLanguageFilenameSuggestions(
        suggestions=["Hello World", "Foo Bar", "Test File"]
    )
    assert len(m.suggestions) == 3


# TC-MOD-011: Exactly 3 suggestions enforced
def test_exactly_three_suggestions_required():
    with pytest.raises(ValidationError):
        FilenameSuggestions(suggestions=["one", "two"])
    with pytest.raises(ValidationError):
        FilenameSuggestions(suggestions=["one", "two", "three", "four"])


# TC-MOD-012: 128 char limit and empty rejection
def test_suggestion_length_and_empty():
    with pytest.raises(ValidationError):
        FilenameSuggestions(suggestions=["a" * 129, "b", "c"])
    with pytest.raises(ValidationError):
        FilenameSuggestions(suggestions=["", "b", "c"])
    with pytest.raises(ValidationError):
        FilenameSuggestions(suggestions=["   ", "b", "c"])


# TC-MOD-013: JSON schema generation
def test_json_schema_generation():
    schema = generate_json_schema_from_model(SnakeCaseFilenameSuggestions)
    assert schema["type"] == "json_schema"
    assert "json_schema" in schema
    assert schema["json_schema"]["name"] == "suggestions"


# TC-MOD-014: get_model_for_naming_convention
def test_get_model_for_naming_convention():
    assert get_model_for_naming_convention("snake_case") is SnakeCaseFilenameSuggestions
    assert get_model_for_naming_convention("camelCase") is CamelCaseFilenameSuggestions
    assert get_model_for_naming_convention("kebab-case") is KebabCaseFilenameSuggestions
    with pytest.raises(ValueError):
        get_model_for_naming_convention("nonexistent")
