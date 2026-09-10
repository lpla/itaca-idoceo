from itaca_idoceo.core import courses_compatible, resolve_course_values


def test_batx_general_and_specific_are_compatible():
    general = "PRIMER BATX"
    specific = "PRIMER BATX. HUMANITATS I CIÈNCIES SOCIALS"
    assert courses_compatible(general, specific)
    selected, compatible = resolve_course_values([general, specific])
    assert compatible
    assert selected == specific


def test_second_batx_general_and_specific_are_compatible():
    general = "SEGON BATX"
    specific = "SEGON BATX HUMANITATS I CIÈNCIES SOCIALS"
    selected, compatible = resolve_course_values([specific, general])
    assert compatible
    assert selected == specific


def test_different_courses_are_not_compatible():
    selected, compatible = resolve_course_values(["PRIMER BATX", "SEGON BATX"])
    assert not compatible
    assert selected in {"PRIMER BATX", "SEGON BATX"}
