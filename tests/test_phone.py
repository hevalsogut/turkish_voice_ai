import pytest

from voiceagent.clinic.phone import normalize_phone, phone_to_speech


@pytest.mark.parametrize(
    "raw",
    ["05540219870", "0554 021 98 70", "+90 554 021 98 70", "5540219870", "00905540219870"],
)
def test_normalize_valid(raw):
    assert normalize_phone(raw) == "05540219870"


@pytest.mark.parametrize("raw", ["", "0554021987", "055402198700", "01540219870", "abc"])
def test_normalize_invalid(raw):
    assert normalize_phone(raw) is None


def test_landline_accepted():
    assert normalize_phone("0216 123 45 67") == "02161234567"


def test_speech_is_natural_turkish_numbers():
    assert phone_to_speech("05540219870") == (
        "sıfır beş yüz elli dört, sıfır yirmi bir, doksan sekiz, yetmiş"
    )


def test_speech_handles_zeros_and_round_numbers():
    assert phone_to_speech("05320000000") == (
        "sıfır beş yüz otuz iki, sıfır sıfır sıfır, sıfır sıfır, sıfır sıfır"
    )
    assert phone_to_speech("02161000105") == "sıfır iki yüz on altı, yüz, sıfır bir, sıfır beş"
