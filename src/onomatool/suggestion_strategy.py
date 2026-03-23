"""Suggestion strategies for different file types.

Strategies encapsulate the multi-pass LLM logic for generating
filename suggestions based on file content and images.
"""

from onomatool.llm_integration import get_suggestions
from onomatool.models import ProcessingResult


class TextOnlyStrategy:
    """Single LLM call with text content only."""

    def get_suggestions(
        self,
        result: ProcessingResult,
        file_path: str,
        image_paths: list[str],
        config: dict,
        verbose_level: int = 0,
    ) -> list[str] | None:
        return get_suggestions(
            result.markdown,
            verbose_level=verbose_level,
            file_path=file_path,
            config=config,
        )


class MultiPassStrategy:
    """Multi-pass LLM strategy for files with images.

    Pass 1: Analyze each image individually (N calls)
    Pass 2: Analyze markdown content with reference image
    Pass 3: Final synthesis combining image and text suggestions
    """

    def get_suggestions(
        self,
        result: ProcessingResult,
        file_path: str,
        image_paths: list[str],
        config: dict,
        verbose_level: int = 0,
    ) -> list[str] | None:
        # Pass 1: Get suggestions from each image
        all_image_suggestions = []
        for img_path in image_paths:
            img_suggestions = get_suggestions(
                "",
                verbose_level=verbose_level,
                file_path=img_path,
                config=config,
            )
            if img_suggestions:
                all_image_suggestions.append(img_suggestions)

        flat_image_suggestions = [
            s for sublist in all_image_suggestions for s in sublist
        ]

        # Pass 2: Analyze markdown content with reference image
        ref_image = image_paths[0]
        md_suggestions = get_suggestions(
            result.markdown,
            verbose_level=verbose_level,
            file_path=ref_image,
            config=config,
        )

        # Pass 3: Final synthesis
        guidance = "\n".join(flat_image_suggestions)
        final_prompt = (
            "You have previously suggested the following file names for each "
            "page/slide/image of the file:\n"
            f"{guidance}\n"
            "Now, based on the full document content (markdown below) and the "
            "above suggestions, generate 3 final file name suggestions that best "
            "represent the entire file.\n"
            f"MARKDOWN:\n{result.markdown}"
        )
        final_suggestions = get_suggestions(
            final_prompt,
            verbose_level=verbose_level,
            file_path=ref_image,
            config=config,
        )

        return final_suggestions or md_suggestions or flat_image_suggestions or None


def select_strategy(
    image_paths: list[str],
) -> TextOnlyStrategy | MultiPassStrategy:
    """Auto-select strategy based on available image paths."""
    if image_paths:
        return MultiPassStrategy()
    return TextOnlyStrategy()
