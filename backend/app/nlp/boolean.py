"""Mesin boolean sederhana untuk kata kunci.

Contoh yang valid:
  "Bank Indonesia" AND (QRIS OR "BI-FAST") AND NOT lowongan

Aturan penulisannya dijelaskan di layar Kata Kunci.
"""

from __future__ import annotations

import re

TOKEN = re.compile(r'"[^"]+"|\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^\s()]+', re.IGNORECASE)


class ExpressionError(ValueError):
    pass


def _tokenize(expression: str) -> list[str]:
    tokens = TOKEN.findall(expression.strip())
    if not tokens:
        raise ExpressionError("Ekspresi kosong")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.index = 0

    def peek(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def pop(self) -> str:
        token = self.peek()
        if token is None:
            raise ExpressionError("Ekspresi terputus")
        self.index += 1
        return token

    def parse(self):
        node = self._or()
        if self.peek() is not None:
            raise ExpressionError(f"Bagian tidak dikenali: {self.peek()}")
        return node

    def _or(self):
        node = self._and()
        while self.peek() and self.peek().upper() == "OR":
            self.pop()
            node = ("or", node, self._and())
        return node

    def _and(self):
        node = self._not()
        while self.peek() and self.peek().upper() == "AND":
            self.pop()
            node = ("and", node, self._not())
        return node

    def _not(self):
        if self.peek() and self.peek().upper() == "NOT":
            self.pop()
            return ("not", self._not())
        return self._primary()

    def _primary(self):
        token = self.pop()
        if token == "(":
            node = self._or()
            if self.pop() != ")":
                raise ExpressionError("Kurung tutup tidak ditemukan")
            return node
        if token.upper() in {"AND", "OR", "NOT", ")"}:
            raise ExpressionError(f"Posisi operator tidak tepat: {token}")
        term = token[1:-1] if token.startswith('"') and token.endswith('"') else token
        if not term:
            raise ExpressionError("Frasa kosong")
        return ("term", term)


def compile_expression(expression: str):
    return _Parser(_tokenize(expression)).parse()


def _contains(term: str, text: str) -> bool:
    return term.casefold() in text.casefold()


def _eval(node, text: str) -> bool:
    kind = node[0]
    if kind == "term":
        return _contains(node[1], text)
    if kind == "not":
        return not _eval(node[1], text)
    if kind == "and":
        return _eval(node[1], text) and _eval(node[2], text)
    if kind == "or":
        return _eval(node[1], text) or _eval(node[2], text)
    raise ExpressionError("Simpul tidak dikenal")


def match_expression(expression: str, text: str) -> bool:
    return _eval(compile_expression(expression), text)


def term_in_text(term: str, text: str) -> bool:
    """Cocokkan satu kata kunci. Frasa dan istilah berhuruf kecil-besar diabaikan.

    Kata pendek seperti BI memakai batas kata agar tidak menempel pada kata lain.
    """
    needle = term.casefold().strip()
    hay = text.casefold()
    if not needle:
        return False
    if " " in needle or needle.startswith("@") or "-" in needle:
        return needle in hay
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay) is not None
