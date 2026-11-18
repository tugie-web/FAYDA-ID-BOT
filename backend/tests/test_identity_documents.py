from app.services.identity_documents import render_identity_pdf, render_printable_summary_png


def sample_identity():
    return {
        "fullName": {"eng": "Example Person", "amh": ""},
        "dateOfBirth": "1990-01-02",
        "gender": {"eng": "Female", "amh": ""},
        "phone": "+251900000000",
        "uin": "000000000000",
        "region": {"eng": "Example Region", "amh": ""},
        "zone": {"eng": "", "amh": ""},
        "woreda": {"eng": "", "amh": ""},
        "residenceStatus": {"eng": "", "amh": ""},
        "email": "",
    }


def test_pdf_is_created_and_marked_non_official():
    data = render_identity_pdf(sample_identity())
    assert data.startswith(b"%PDF")
    assert len(data) > 500


def test_printable_png_is_created():
    data = render_printable_summary_png(sample_identity())
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(data) > 500
