"""How two spellings of one name compare, for every layer (storage included)."""

import unicodedata


def normalize(name: str) -> str:
    """Casefolded, accent-free, single-spaced: "Élodie " and "elodie" are one name.

    A voice transcript rarely spells a name the way it was typed.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(bare.casefold().split())
