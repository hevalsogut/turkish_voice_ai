"""Phone number validation and speech formatting, done in code because LLMs misread digits."""

import re

_DIGIT_WORDS = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]


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


def phone_to_speech(phone: str) -> str:
    """'05540219870' -> 'sıfır beş beş dört, sıfır iki bir, dokuz sekiz, yedi sıfır'."""
    groups = [phone[:4], phone[4:7], phone[7:9], phone[9:11]]
    return ", ".join(" ".join(_DIGIT_WORDS[int(d)] for d in g) for g in groups)
