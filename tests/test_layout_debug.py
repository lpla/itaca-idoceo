from itaca_idoceo.layout_debug import sanitize_word


def test_sanitize_keeps_only_safe_structural_labels():
    assert sanitize_word("MATÈRIA") == "MATERIA"
    assert sanitize_word("MÒDUL") == "MODUL"
    assert sanitize_word("REPETIX") == "REPETIX"
    assert sanitize_word("R") == "R"


def test_sanitize_masks_personal_or_free_text():
    assert "Martínez" not in sanitize_word("Martínez,")
    assert sanitize_word("123456789") == "<NUM:9>"
    assert sanitize_word("23", ordinal_position=True) == "ORDE=23"
