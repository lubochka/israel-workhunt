"""Local recipient-aware draft review. No messages, uploads or transport."""
import copy
import datetime as dt
import re
from records import timestamp, url_identity
from profile_config import private_root, private_path, safe_output


def supported_text(value):
    return isinstance(value, str) and bool(value.strip())

MODES = {
    "employer": {"stage": "vacancy_application", "parts": ["exact_role", "requirement", "supported_example", "contribution", "next_step"]},
    "client": {"stage": "project_proposal", "parts": ["client_outcome", "supported_example", "first_deliverable", "acceptance_criterion", "unresolved_scope"]},
    "network": {"stage": "network_admission", "parts": ["specialization", "representative_engagements", "individual_contribution", "supported_preferences"]},
    "agency": {"stage": "agency_screening", "parts": ["exact_role", "hands_on_ownership", "team_contribution", "supported_example", "next_stage"]},
}
ATTACHMENT_CLAIM = re.compile(r"\b(?:I(?:'ve| have)? attached|attached (?:is |are )?(?:my |the |a )?(?:CV|resume)|(?:my |the |a )?(?:CV|resume) (?:is |has been )?(?:attached|enclosed)|please find attached)\b|מצורפ(?:ים|ות|ת)?\s+(?:בזאת\s+)?קורות\s+חיים", re.I)
PLACEHOLDER = re.compile(r"\[[^\]\n]+\](?!\()|\{\{[^}]+\}\}|<[A-Z_ ]+>")
SUBMISSION_CLAIM = re.compile(r"\b(?:I (?:have |already )?(?:submitted|sent) (?:my |the |an? )?application|my application (?:was|has been) (?:submitted|sent))\b|הגשתי\s+מועמדות", re.I)


def prepare_draft(draft, opportunity_id=None, cv=None, portfolio=None, now=None):
    result = copy.deepcopy(draft)
    mode = result.get("recipient_type", "employer")
    if mode not in MODES:
        raise ValueError("Unknown draft recipient_type")
    expected = MODES[mode]
    stage = result.get("stage", expected["stage"])
    if stage != expected["stage"]:
        raise ValueError("Draft stage contradicts recipient type")
    text = result.get("text", "")
    if not isinstance(text, str):
        raise ValueError("Draft text must be a string")
    issues = []
    if not text.strip():
        issues.append("Draft text is empty")
    if PLACEHOLDER.search(text):
        issues.append("Unresolved placeholders remain; draft is not ready")
    if mode != "network" and not supported_text(opportunity_id):
        issues.append("Exact opportunity identity required")
    if not supported_text(result.get("recipient_evidence")):
        issues.append("Recipient/channel has not been observed")
    parts = result.get("content_evidence", {})
    if not isinstance(parts, dict):
        raise ValueError("content_evidence must be an object")
    issues.extend("Missing supported drafting element: " + k for k in expected["parts"] if not supported_text(parts.get(k)))
    limit = result.get("observed_character_limit")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("Character limit must be observed positive integer or null")
    if limit and len(text) > limit:
        issues.append("Draft exceeds the observed field limit")
    attachment = result.get("attachment_evidence", {})
    cv = cv or {}
    observed = timestamp(attachment.get("at")) if isinstance(attachment, dict) else None
    now = now or dt.datetime.now(dt.timezone.utc)
    submission = result.get("submission_evidence", {})
    submitted_at = timestamp(submission.get("at")) if isinstance(submission, dict) else None
    submitted = bool(isinstance(submission, dict) and opportunity_id and submission.get("opportunity_id") == opportunity_id
                     and submission.get("status") in {"submitted_observed", "receipt_observed"} and supported_text(submission.get("evidence"))
                     and submitted_at and submitted_at.timestamp() <= now.timestamp())
    if SUBMISSION_CLAIM.search(text) and not submitted:
        issues.append("Unsupported submission claim; this local draft is not sent")
    claims = result.get("claim_review", {})
    if not isinstance(claims, dict):
        raise ValueError("claim_review must be an object")
    for key in ("experience_supported", "terms_supported_or_omitted", "language_confirmed", "submission_wording_checked"):
        if claims.get(key) is not True or not supported_text(claims.get("evidence")):
            issues.append("Evidence-backed wording review required: " + key)
    attached = bool(isinstance(attachment, dict) and opportunity_id and cv.get("current_sha256")
                    and attachment.get("opportunity_id") == opportunity_id
                    and attachment.get("sha256") == cv["current_sha256"]
                    and attachment.get("status") == "uploaded_observed" and supported_text(attachment.get("evidence"))
                    and observed and observed.timestamp() <= now.timestamp())
    if ATTACHMENT_CLAIM.search(text) and not attached:
        issues.append("Unsupported CV-attachment claim; selected/prepared is not uploaded")
    quality = result.get("attachment_quality", {})
    if not isinstance(quality, dict):
        raise ValueError("attachment_quality must be an object")
    if result.get("attachment_intended"):
        if cv.get("file_status") != "hash_matches":
            issues.append("Attachment file unavailable or differs from selected manifest version")
        if cv.get("ready_to_attach") is not True or cv.get("content_reviewed") is not True or cv.get("unresolved_facts"):
            issues.append("Selected CV is unreviewed, unresolved or not ready to attach")
        content_review = cv.get("content_review") or {}
        if not (isinstance(content_review, dict) and content_review.get("status") == "reviewed"
                and content_review.get("sha256") == cv.get("current_sha256") and supported_text(content_review.get("evidence"))):
            issues.append("Selected CV content review must identify the measured file")
        if not (supported_text(cv.get("version_id")) and quality.get("version_id") == cv["version_id"]
                and supported_text(cv.get("current_sha256")) and quality.get("sha256") == cv["current_sha256"]):
            issues.append("Attachment quality evidence must identify the selected CV version and measured hash")
        for key in ("content_reviewed", "render_reviewed", "role_language_confirmed", "no_unresolved_material_facts"):
            if quality.get(key) is not True or not supported_text(quality.get("evidence")):
                issues.append("Attachment quality not established: " + key)
    handoff = []
    for entry in portfolio or []:
        if not isinstance(entry, dict):
            raise ValueError("Portfolio handoff entries must be objects")
        missing = [key for key in ("selected_for", "individual_contribution", "evidence", "visibility") if not supported_text(entry.get(key))]
        public = entry.get("visibility") == "public" and bool(url_identity(entry.get("source_url")))
        narrative = entry.get("visibility") == "anonymized_narrative" and entry.get("redaction_reviewed") is True
        handoff.append({**copy.deepcopy(entry), "ready_for_draft": not missing and (public or narrative), "missing": missing})
        if missing or not (public or narrative):
            issues.append("Portfolio evidence requires contribution, relevance and disclosure review")
    result.update(recipient_type=mode, stage=stage, state="not_sent", opportunity_id=opportunity_id,
                  counts_as_opportunity=False if mode == "network" else None,
                  character_count=len(text), portfolio_handoff=handoff,
                  attachment_check={"observed_uploaded": attached, "quality": copy.deepcopy(quality)},
                  review={"ready_for_use": not issues, "issues": issues, "external_action_authorized": False})
    return result


def write_draft(workdir, input_path, output_path):
    """Prepare one private artifact without a configured profile or external action."""
    import json
    root = private_root(workdir)
    request_path = private_path(root, input_path)
    output = safe_output(root, output_path, extra_protected=[request_path])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = prepare_draft(request["draft"], request.get("opportunity_id"), request.get("cv"), request.get("portfolio_evidence"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return result


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path, help="Project or private .workhunt directory")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = write_draft(args.workdir, args.input, args.output)
    print(json.dumps({"output": str(args.output), "state": "not_sent", "ready_for_use": result["review"]["ready_for_use"]}))
