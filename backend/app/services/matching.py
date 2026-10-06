"""Pencarian kata kunci inklusi dan eksklusi pada sebuah teks."""

from __future__ import annotations

from app.models import Keyword
from app.nlp.boolean import ExpressionError, match_expression, term_in_text


def matched_terms(text: str, keywords: list[Keyword]) -> list[str]:
    hits = []
    for keyword in keywords:
        if keyword.is_active and keyword.mode == "inklusi" and term_in_text(keyword.term, text):
            hits.append(keyword.term)
    return hits


def excluded(text: str, keywords: list[Keyword]) -> bool:
    return any(
        keyword.is_active and keyword.mode == "eksklusi" and term_in_text(keyword.term, text)
        for keyword in keywords
    )


def passes_saved_queries(text: str, queries: list) -> bool:
    active = [query for query in queries if query.is_active]
    if not active:
        return True
    for query in active:
        try:
            if match_expression(query.expression, text):
                return True
        except ExpressionError:
            continue
    return False
