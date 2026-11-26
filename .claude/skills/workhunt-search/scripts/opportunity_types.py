"""Separate identified work from admission; a response mode is not the work itself."""
from records import url_identity

SOURCE_ACCESS_KINDS = {"source_access", "network_admission", "generic_screening", "platform_invitation", "profile", "service"}
SOURCE_ACCESS_MODES = {"network_admission", "generic_agency_screening", "platform_invitation"}


def supported_text(value):
    return isinstance(value, str) and bool(value.strip())


def first_text(record, *keys):
    return next((record[key] for key in keys if supported_text(record.get(key))), None)


def identified_project(record, review=None):
    review = review if isinstance(review, dict) else {}
    return bool(record.get("type") == "project"
                and record.get("record_kind") not in SOURCE_ACCESS_KINDS
                and first_text(record, "id", "opportunity_id")
                and url_identity(first_text(record, "url", "listing_url", "source_url"))
                and first_text(record, "company", "employer_or_client")
                and (first_text(record, "description", "description_evidence") or first_text(review, "description_evidence")))


def source_access_record(record, review=None):
    return (record.get("record_kind") in SOURCE_ACCESS_KINDS
            or record.get("response_mode") in SOURCE_ACCESS_MODES
            or record.get("response_mode") == "client_invitation" and not identified_project(record, review))
