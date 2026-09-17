from itaca_idoceo.gui import AUTHOR_NAME, ISSUES_URL, PORTFOLIO_URL, REPOSITORY_URL


def test_gui_public_links_are_explicit_and_https():
    assert AUTHOR_NAME == "Leopoldo Pla Sempere"
    assert PORTFOLIO_URL == "https://lpla.github.io"
    assert REPOSITORY_URL == "https://github.com/lpla/itaca-idoceo"
    assert ISSUES_URL == "https://github.com/lpla/itaca-idoceo/issues/new"
