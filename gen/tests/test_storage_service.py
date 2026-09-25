import uuid

from backend.services.storage_service import document_storage_path


def test_document_storage_path_does_not_include_unsafe_original_filename():
    user_id = uuid.UUID("982b5111-8351-4684-bbae-c209cda81619")
    document_id = uuid.UUID("ed1786df-ea56-4c3e-9af6-f2eef447f24b")

    path = document_storage_path(user_id, document_id)

    assert path == (
        "documents/982b5111-8351-4684-bbae-c209cda81619/"
        "ed1786df-ea56-4c3e-9af6-f2eef447f24b/source.pdf"
    )
    assert path.isascii()
