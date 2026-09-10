from itaca_idoceo.core import VisualWord, has_itaca3_report_signature


def vw(text: str, x: float, y: float = 100.0) -> VisualWord:
    return VisualWord(text=text, x0=x, y0=y, x1=x + 20, y1=y + 10)


def test_itaca3_signature_accepts_all_five_headers_on_same_row():
    words = [
        vw("ORDE", 0),
        vw("NIA", 60),
        vw("REPETIX", 120),
        vw("COGNOMS", 220),
        vw("I", 310),
        vw("NOM", 340),
        vw("MATÈRIA", 440),
    ]
    assert has_itaca3_report_signature(words)


def test_itaca3_signature_requires_all_headers():
    words = [
        vw("ORDE", 0),
        vw("NIA", 60),
        vw("COGNOMS", 220),
        vw("I", 310),
        vw("NOM", 340),
        vw("MATÈRIA", 440),
    ]
    assert not has_itaca3_report_signature(words)


def test_itaca3_signature_requires_a_single_visual_header_row():
    words = [
        vw("ORDE", 0, 100),
        vw("NIA", 60, 100),
        vw("REPETIX", 120, 100),
        vw("COGNOMS", 220, 100),
        vw("I", 310, 130),
        vw("NOM", 340, 100),
        vw("MATÈRIA", 440, 100),
    ]
    assert not has_itaca3_report_signature(words)


def test_itaca3_signature_accepts_fp_modul_header_without_repetix():
    words = [
        vw("ORDE", 0),
        vw("NIA", 60),
        vw("COGNOMS", 180),
        vw("I", 270),
        vw("NOM", 300),
        vw("MÒDUL", 420),
    ]
    assert has_itaca3_report_signature(words)
