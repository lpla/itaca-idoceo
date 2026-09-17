from itaca_idoceo.cli import build_parser


def test_convert_accepts_multiple_files_and_folders():
    args = build_parser().parse_args(
        [
            "convert",
            "references",
            "photo-a.pdf",
            "photo-b.pdf",
            "--include-repetix",
            "--include-materia",
        ]
    )

    assert args.command == "convert"
    assert [str(path) for path in args.inputs] == [
        "references",
        "photo-a.pdf",
        "photo-b.pdf",
    ]
    assert args.include_repetix is True
    assert args.include_materia is True
    assert args.no_nia is False
