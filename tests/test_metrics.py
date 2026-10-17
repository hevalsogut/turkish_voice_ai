from voiceagent.bench.metrics import cer, normalize, wer


def test_normalize_turkish_casing_and_punctuation():
    assert normalize("IŞIK, İstanbul!") == "ışık istanbul"


def test_wer_identical_is_zero():
    assert wer("Merhaba, randevu almak istiyorum.", "merhaba randevu almak istiyorum") == 0.0


def test_wer_counts_substitution():
    assert wer("bir iki üç dört", "bir iki üç beş") == 0.25


def test_wer_deletion_and_empty_hypothesis():
    assert wer("bir iki", "") == 1.0


def test_cer_small_typo():
    assert 0 < cer("randevu", "randevü") < 0.2
