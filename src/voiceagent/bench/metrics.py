import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def turkish_lower(text: str) -> str:
    # str.lower() maps "I" -> "i" and "İ" -> "i̇"; Turkish needs "I" -> "ı", "İ" -> "i".
    return text.replace("İ", "i").replace("I", "ı").lower()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = turkish_lower(text)
    text = _PUNCT.sub(" ", text)
    return " ".join(text.split())


def _edit_distance(ref: list[str], hyp: list[str]) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def wer(reference: str, hypothesis: str) -> float:
    ref = normalize(reference).split()
    hyp = normalize(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def cer(reference: str, hypothesis: str) -> float:
    ref = list(normalize(reference).replace(" ", ""))
    hyp = list(normalize(hypothesis).replace(" ", ""))
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)
