from typing import Any, Dict


def _normalize_text(value: Any) -> str:
    """Normalize text values to stable UTF-8 strings for UI rendering."""
    if value is None:
        return ""
    text = str(value)
    try:
        return text.encode("utf-8", errors="replace").decode("utf-8")
    except Exception:
        return text


def _build_default_detail_data(
    image_path: str,
    command_line: str,
    category: str,
    timestamp: str,
    publisher: str,
    company: str,
    file_size: str,
    file_version: str,
    sha256: str,
) -> Dict[str, Any]:
    return {
        "image_path": image_path,
        "command_line": command_line,
        "category": category,
        "timestamp": timestamp,
        "signature": "Unsigned",
        "publisher": publisher,
        "company": company,
        "size": file_size,
        "version": file_version,
        "hash": sha256,
    }


def map_to_model_entry(entry: Any) -> Dict[str, Any]:
    """Map AutorunEntry object or dict into the UI model entry schema."""
    if hasattr(entry, "entry"):
        entry_val = getattr(entry, "entry", "")
        description = getattr(entry, "description", "")
        publisher = getattr(entry, "publisher", "")
        company = getattr(entry, "company", "")
        image_path = getattr(entry, "image_path", "")
        timestamp = getattr(entry, "timestamp", "")
        category = getattr(entry, "category", "")
        location = getattr(entry, "location", "")
        enabled = getattr(entry, "enabled", "")
        signer_status = getattr(entry, "signer_status", "")
        launch_string = getattr(entry, "launch_string", "")
        command_line = getattr(entry, "command_line", "") or launch_string
        signature_detail = getattr(entry, "signature_detail", "")
        sha256 = getattr(entry, "sha256", "")
        file_size = getattr(entry, "file_size", "")
        file_version = getattr(entry, "file_version", "")
        service_name = getattr(entry, "service_name", "")
        file_exists = getattr(entry, "file_exists", True)

        detail_data = None
        if hasattr(entry, "get_detail_data"):
            detail_data = entry.get_detail_data()
    else:
        data = entry if isinstance(entry, dict) else {}
        entry_val = data.get("entry", "")
        description = data.get("description", "")
        publisher = data.get("publisher", "")
        company = data.get("company", "")
        image_path = data.get("image_path", "")
        timestamp = data.get("timestamp", "")
        category = data.get("category", "")
        location = data.get("location", "")
        enabled = data.get("enabled", "")
        signer_status = data.get("signer_status", "")
        launch_string = data.get("launch_string", "")
        command_line = data.get("command_line", "") or launch_string
        signature_detail = data.get("signature_detail", "")
        sha256 = data.get("sha256", "")
        file_size = data.get("file_size", "")
        file_version = data.get("file_version", "")
        service_name = data.get("service_name", "")
        file_exists = data.get("file_exists", True)
        detail_data = data.get("detail_data")

    publisher = _normalize_text(publisher)
    company = _normalize_text(company)

    if isinstance(detail_data, dict):
        detail = dict(detail_data)
        if detail.get("publisher"):
            detail["publisher"] = _normalize_text(detail.get("publisher"))
        else:
            detail["publisher"] = publisher
        if detail.get("company"):
            detail["company"] = _normalize_text(detail.get("company"))
        else:
            detail["company"] = company
    else:
        detail = _build_default_detail_data(
            image_path=image_path,
            command_line=command_line,
            category=category,
            timestamp=timestamp,
            publisher=publisher,
            company=company,
            file_size=file_size,
            file_version=file_version,
            sha256=sha256,
        )

    return {
        "entry": entry_val,
        "description": description,
        "publisher": publisher,
        "company": company,
        "image_path": image_path,
        "timestamp": timestamp,
        "category": category,
        "location": location,
        "enabled": enabled,
        "signer_status": signer_status,
        "launch_string": launch_string,
        "command_line": command_line,
        "signature_detail": signature_detail,
        "sha256": sha256,
        "file_size": file_size,
        "file_version": file_version,
        "service_name": service_name,
        "file_exists": file_exists,
        "detail_data": detail,
    }

