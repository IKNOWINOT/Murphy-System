from __future__ import annotations

from .polyglot_bot import context_aware_translate
from .comment_classifier import classify_line


class CodeTranslatorBot:
    def translate_block(self, text: str, target_lang: str) -> str:
        result = context_aware_translate(text, target_lang)
        return result.translated

    def classify(self, line: str) -> str:
        return classify_line(line)
