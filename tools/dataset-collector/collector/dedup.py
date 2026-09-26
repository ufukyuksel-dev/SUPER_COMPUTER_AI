import hashlib


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _shingles(text: str, k: int = 5) -> set:
    words = _normalize(text).split()
    if len(words) <= k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cross_split_check(splits: dict, near_threshold: float = 0.8) -> list:
    """Find exact and near duplicates shared across splits.

    splits: {"train": [text, ...], "validation": [text, ...], ...}
    Returns findings: {"kind": "exact"|"near", "splits": (a, b), "indices": (i, j)}.
    """
    findings = []
    names = sorted(splits)
    hashed = {
        name: [hashlib.sha256(_normalize(t).encode()).hexdigest() for t in splits[name]]
        for name in names
    }
    shingled = {name: [_shingles(t) for t in splits[name]] for name in names}

    for ai in range(len(names)):
        for bi in range(ai + 1, len(names)):
            a, b = names[ai], names[bi]
            b_hash_index = {}
            for j, digest in enumerate(hashed[b]):
                b_hash_index.setdefault(digest, []).append(j)
            for i, digest in enumerate(hashed[a]):
                for j in b_hash_index.get(digest, []):
                    findings.append(
                        {"kind": "exact", "splits": (a, b), "indices": (i, j)}
                    )
            for i, sh_a in enumerate(shingled[a]):
                for j, sh_b in enumerate(shingled[b]):
                    if hashed[a][i] == hashed[b][j]:
                        continue  # already reported as exact
                    if jaccard(sh_a, sh_b) >= near_threshold:
                        findings.append(
                            {"kind": "near", "splits": (a, b), "indices": (i, j)}
                        )
    return findings
