import re


IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def quote_ident(identifier: str) -> str:
    if not IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier}")
    return f'"{identifier}"'


def normalize_identifier(identifier: str) -> str:
    return identifier.strip().strip('"').lower()
