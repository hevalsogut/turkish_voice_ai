"""Phone number validation and speech formatting, done in code because LLMs misread digits."""

import re

_ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]


def normalize_phone(raw: str) -> str | None:
    """Return an 11-digit Turkish number like 05540219870, or None if it isn't valid."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0090"):
        digits = digits[4:]
    elif digits.startswith("90") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10 and digits[0] in "2345":
        digits = "0" + digits
    if len(digits) == 11 and digits[0] == "0" and digits[1] in "2345":
        return digits
    return None


def _number_words(n: int) -> str:
    """0-999 in Turkish words: 554 -> 'beş yüz elli dört', 70 -> 'yetmiş'."""
    hundreds, rest = divmod(n, 100)
    tens, ones = divmod(rest, 10)
    parts = []
    if hundreds:
        parts.append(("" if hundreds == 1 else _ONES[hundreds] + " ") + "yüz")
    if tens:
        parts.append(_TENS[tens])
    if ones:
        parts.append(_ONES[ones])
    return " ".join(parts) or "sıfır"


def _group_words(group: str) -> str:
    """Speak a digit group as a number, leading zeros one by one: '021' -> 'sıfır yirmi bir'."""
    stripped = group.lstrip("0")
    zeros = ["sıfır"] * (len(group) - len(stripped))
    if not stripped:
        return " ".join(zeros)
    return " ".join([*zeros, _number_words(int(stripped))])


def phone_to_speech(phone: str) -> str:
    """The way Turks read numbers aloud:
    '05540219870' -> 'sıfır beş yüz elli dört, sıfır yirmi bir, doksan sekiz, yetmiş'.
    """
    groups = [phone[1:4], phone[4:7], phone[7:9], phone[9:11]]
    first = "sıfır " + _group_words(groups[0])
    return ", ".join([first, *(_group_words(g) for g in groups[1:])])
