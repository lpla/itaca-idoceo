from pathlib import Path

from itaca_idoceo.core import ClassResult, PageMetadata, PdfResult, Student
from itaca_idoceo.photo_reference_cache import match_photo_result_to_parsed_references
from itaca_idoceo.photo_roster import PhotoRosterPageSummary, PhotoRosterResult, PhotoRosterStudent


def test_parsed_reference_pool_matches_without_reopening_pdfs():
    photo_student = PhotoRosterStudent(
        page=1, ordinal=1, row=1, column=1,
        full_name="ALPHA, BETA", surnames="ALPHA", given_names="BETA",
        xref=1, image_x0=0, image_y0=0, image_x1=10, image_y1=10, name_lines=1,
    )
    photo = PhotoRosterResult(
        source=Path("photo.pdf"), page_count=1, students=[photo_student],
        pages=[PhotoRosterPageSummary(1, 1, 1, 1, 1, 0, 0)], issues=[],
        group_raw="GROUP A", group_code="GROUP A",
    )
    reference_student = Student(
        page=1, block=1, ordinal=1, nia="ID001",
        full_name="ALPHA, BETA", surnames="ALPHA", given_names="BETA",
        row_x=0.0, visual_y=1.0,
    )
    source = Path("reference.pdf")
    reference_class = ClassResult(
        source=source,
        metadata=PageMetadata(group_raw="GROUP A", group_code="GROUP A"),
        students=[reference_student], issues=[],
    )
    reference = PdfResult(
        source=source, classes=[reference_class], page_count=1, issues=[],
        report_signature=True, signature_pages=(1,),
    )

    result = match_photo_result_to_parsed_references(photo, [reference])

    assert result.match.matched_photos == 1
    assert result.match.links[0].method == "exact"
    assert result.reference_by_photo_ordinal()[1].nia == "ID001"
    assert result.usable_files == 1
    assert result.valid_classes == 1
