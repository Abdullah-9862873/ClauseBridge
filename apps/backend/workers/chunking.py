import re
_CLAUSE_PATTERN = re.compile(
    r"(?m)^\s*((?:[0-9]+(?:\.[0-9]+)*\.?|\([a-z0-9]+\)|Section\s+[0-9]+|Article\s+[IVXLCDM]+))\s+"
)
def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
def _split_by_clauses(para: str) -> list[str]:
    matches = list(_CLAUSE_PATTERN.finditer(para))
    if len(matches) < 2:
        return [para]
    chunks: list[str] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(para)
        chunks.append(para[m.start():end].strip())
    return [c for c in chunks if c]
def split_into_chunks(text: str) -> list[str]:
    result: list[str] = []
    for para in _split_paragraphs(text):
        result.extend(_split_by_clauses(para))
    return result