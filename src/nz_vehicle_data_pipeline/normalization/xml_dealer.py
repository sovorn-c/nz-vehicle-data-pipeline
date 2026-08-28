"""Bounded and guarded XML parser for synthetic dealer listings (e04s02, ADR 0005)."""

import xml.etree.ElementTree as ET
from typing import Any

MAX_DEALER_XML_BYTES: int = 262144  # 256 KiB
FORBIDDEN_DECLARATIONS: tuple[str, ...] = ("<!DOCTYPE", "<!ENTITY", "SYSTEM", "PUBLIC")
XML_SCALAR_ELEMENTS = {
    "dealer_id",
    "listing_id",
    "vin",
    "price_cents",
    "odometer_km",
    "currency",
    "condition",
    "availability",
    "make",
    "model",
    "model_year",
    "trim",
    "asking_price_nzd",
    "description",
    "listing_url",
    "listed_at",
    "updated_at",
}
XML_METADATA_ELEMENTS = {
    "synthetic",
    "dataset_id",
    "dataset_version",
    "scenario_id",
    "generated_at",
    "disclaimer",
}


def parse_dealer_xml(payload: str) -> dict[str, Any]:
    """Parse single dealer listing XML with size, declaration, duplicate, and root guards."""
    raw_bytes = payload.encode("utf-8")
    if len(raw_bytes) > MAX_DEALER_XML_BYTES:
        msg = (
            f"XML payload size ({len(raw_bytes)} bytes) exceeds "
            f"maximum allowed size ({MAX_DEALER_XML_BYTES} bytes)"
        )
        raise ValueError(msg)

    payload_upper = payload.upper()
    for forbidden in FORBIDDEN_DECLARATIONS:
        if forbidden in payload_upper:
            msg = f"Forbidden XML declaration detected: {forbidden}"
            raise ValueError(msg)

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        msg = f"Malformed XML structure: {exc}"
        raise ValueError(msg) from exc

    if root.tag not in {"dealer-listing", "dealer_listing"}:
        msg = f"Expected root element 'dealer-listing', got '{root.tag}'"
        raise ValueError(msg)

    seen_scalars: set[str] = set()
    data: dict[str, Any] = {}

    for child in root:
        tag = child.tag.replace("-", "_")
        if tag == "image_urls":
            urls: list[str] = []
            for image in child:
                image_tag = image.tag.replace("-", "_")
                if image_tag not in {"image_url", "url"} or len(image):
                    raise ValueError(f"Unknown nested XML element: <{image.tag}>")
                if image.text:
                    urls.append(image.text.strip())
            data["image_urls"] = urls
        elif tag == "metadata":
            meta_dict: dict[str, Any] = {}
            for mchild in child:
                mtag = mchild.tag.replace("-", "_")
                if mtag not in XML_METADATA_ELEMENTS or len(mchild):
                    raise ValueError(f"Unknown nested XML element: <{mchild.tag}>")
                val_str = (mchild.text or "").strip()
                if mtag == "synthetic":
                    meta_dict[mtag] = val_str.lower() in {"true", "1"}
                else:
                    meta_dict[mtag] = val_str
            data["metadata"] = meta_dict
        else:
            if tag not in XML_SCALAR_ELEMENTS or len(child):
                raise ValueError(f"Unknown XML element: <{child.tag}>")
            if tag in seen_scalars:
                msg = f"Duplicate XML element: <{child.tag}>"
                raise ValueError(msg)
            seen_scalars.add(tag)
            data[tag] = (child.text or "").strip()

    return data
