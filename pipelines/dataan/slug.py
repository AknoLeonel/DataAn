import re
import unicodedata


def slugify(text: str) -> str:
    """'São Paulo' -> 'sao-paulo'."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
