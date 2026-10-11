"""
xml_validator.py
================
XML schema validation for the three DPP payload types (Section 3.1).

Three schemas:
  RawMaterialRecord  — upstream material composition and certification data
  ProductionRecord   — IoT-measured ESG metrics at manufacture
  LifecycleEvent     — repair logs, resale transactions, recycling referrals

All schemas align with GS1 Digital Link v1.2 [23].
Malformed or incomplete records are rejected at the schema layer before
being passed to the TokenSmartContract (error code: SCHEMA_VALIDATION_FAILED).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Required fields per schema (GS1 Digital Link v1.2 — textile profile)
# ─────────────────────────────────────────────────────────────────────────────

RAW_MATERIAL_REQUIRED = {
    "product_id", "garment_type",
    "material_composition", "origin_region",
    "gots_certification", "spare_parts_available",
}

PRODUCTION_REQUIRED = {
    "total_co2_kg_equiv", "recycled_content_pct",
    "repairability_score", "renewable_energy_pct",
    "worker_safety_incidents", "iot_benchmark",
}

LIFECYCLE_EVENT_REQUIRED = {
    "dpp_id", "event_type",
}


# ─────────────────────────────────────────────────────────────────────────────
# Validation result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    is_valid: bool
    schema_type: str
    parsed_data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    error_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "schema_type": self.schema_type,
            "errors": self.errors,
            "error_code": self.error_code,
            "parsed_data": self.parsed_data,
        }


# ─────────────────────────────────────────────────────────────────────────────
# XMLSchemaValidator
# ─────────────────────────────────────────────────────────────────────────────

class XMLSchemaValidator:
    """
    Validates DPP XML payloads.

    Usage:
        validator = XMLSchemaValidator()
        result = validator.validate_raw_material(xml_string)
        if result.is_valid:
            data = result.parsed_data
    """

    # ------------------------------------------------------------------
    # Public validate methods
    # ------------------------------------------------------------------

    def validate_raw_material(self, xml_input) -> ValidationResult:
        """Validate a RawMaterialRecord XML string or dict."""
        if isinstance(xml_input, dict):
            data = xml_input
        else:
            try:
                data = self._parse_xml(xml_input)
            except ET.ParseError as exc:
                return ValidationResult(
                    is_valid=False,
                    schema_type="RawMaterialRecord",
                    errors=[f"XML parse error: {exc}"],
                    error_code="SCHEMA_VALIDATION_FAILED",
                )

        errors = self._check_required(data, RAW_MATERIAL_REQUIRED, "RawMaterialRecord")
        errors += self._validate_raw_material_types(data)

        return ValidationResult(
            is_valid=len(errors) == 0,
            schema_type="RawMaterialRecord",
            parsed_data=data,
            errors=errors,
            error_code="SCHEMA_VALIDATION_FAILED" if errors else "",
        )

    def validate_production(self, xml_input) -> ValidationResult:
        """Validate a ProductionRecord XML string or dict."""
        if isinstance(xml_input, dict):
            data = xml_input
        else:
            try:
                data = self._parse_xml(xml_input)
            except ET.ParseError as exc:
                return ValidationResult(
                    is_valid=False,
                    schema_type="ProductionRecord",
                    errors=[f"XML parse error: {exc}"],
                    error_code="SCHEMA_VALIDATION_FAILED",
                )

        errors = self._check_required(data, PRODUCTION_REQUIRED, "ProductionRecord")
        errors += self._validate_production_types(data)

        return ValidationResult(
            is_valid=len(errors) == 0,
            schema_type="ProductionRecord",
            parsed_data=data,
            errors=errors,
            error_code="SCHEMA_VALIDATION_FAILED" if errors else "",
        )

    def validate_lifecycle_event(self, xml_input) -> ValidationResult:
        """Validate a LifecycleEvent XML string or dict."""
        if isinstance(xml_input, dict):
            data = xml_input
        else:
            try:
                data = self._parse_xml(xml_input)
            except ET.ParseError as exc:
                return ValidationResult(
                    is_valid=False,
                    schema_type="LifecycleEvent",
                    errors=[f"XML parse error: {exc}"],
                    error_code="SCHEMA_VALIDATION_FAILED",
                )

        errors = self._check_required(data, LIFECYCLE_EVENT_REQUIRED, "LifecycleEvent")

        return ValidationResult(
            is_valid=len(errors) == 0,
            schema_type="LifecycleEvent",
            parsed_data=data,
            errors=errors,
            error_code="SCHEMA_VALIDATION_FAILED" if errors else "",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_xml(self, xml_str: str) -> Dict[str, Any]:
        """Parse flat XML into a dict; nested <material_composition> becomes a sub-dict."""
        root = ET.fromstring(xml_str.strip())
        data: Dict[str, Any] = {}
        for child in root:
            if len(child) > 0:               # nested element
                data[child.tag] = {
                    grandchild.tag: self._coerce(grandchild.text)
                    for grandchild in child
                }
            else:
                data[child.tag] = self._coerce(child.text)
        return data

    @staticmethod
    def _coerce(value: Optional[str]) -> Any:
        """Best-effort coercion: int → float → bool → str."""
        if value is None:
            return None
        v = value.strip()
        if v.lower() == "true":
            return True
        if v.lower() == "false":
            return False
        try:
            return int(v)
        except ValueError:
            pass
        try:
            return float(v)
        except ValueError:
            pass
        return v

    @staticmethod
    def _check_required(
        data: Dict[str, Any], required: set, schema_name: str
    ) -> List[str]:
        errors = []
        for field_name in required:
            if field_name not in data or data[field_name] is None:
                errors.append(
                    f"{schema_name}: missing required field '{field_name}'"
                )
        return errors

    @staticmethod
    def _validate_raw_material_types(data: Dict[str, Any]) -> List[str]:
        errors = []
        if "material_composition" in data and not isinstance(
            data["material_composition"], dict
        ):
            errors.append("RawMaterialRecord: 'material_composition' must be a nested element")
        return errors

    @staticmethod
    def _validate_production_types(data: Dict[str, Any]) -> List[str]:
        errors = []
        numeric_fields = [
            "total_co2_kg_equiv", "recycled_content_pct",
            "repairability_score", "renewable_energy_pct",
        ]
        for f in numeric_fields:
            if f in data:
                try:
                    float(data[f])
                except (TypeError, ValueError):
                    errors.append(f"ProductionRecord: '{f}' must be numeric")
        return errors


# ─────────────────────────────────────────────────────────────────────────────
# Canonical XML builders (for scenario runners)
# ─────────────────────────────────────────────────────────────────────────────

def build_raw_material_xml(
    product_id: str,
    garment_type: str,
    recycled_polyester_pct: float,
    organic_cotton_pct: float,
    elastane_pct: float,
    origin_region: str,
    gots_certification: str,
    spare_parts_available: bool,
) -> str:
    """Return a GS1-conformant RawMaterialRecord XML string."""
    spare = "true" if spare_parts_available else "false"
    return f"""<RawMaterialRecord>
  <product_id>{product_id}</product_id>
  <garment_type>{garment_type}</garment_type>
  <material_composition>
    <recycled_polyester_pct>{recycled_polyester_pct}</recycled_polyester_pct>
    <organic_cotton_pct>{organic_cotton_pct}</organic_cotton_pct>
    <elastane_pct>{elastane_pct}</elastane_pct>
  </material_composition>
  <recycled_content_pct>{recycled_polyester_pct}</recycled_content_pct>
  <origin_region>{origin_region}</origin_region>
  <gots_certification>{gots_certification}</gots_certification>
  <spare_parts_available>{spare}</spare_parts_available>
</RawMaterialRecord>"""


def build_production_xml(
    product_id: str,
    total_co2_kg_equiv: float,
    recycled_content_pct: float,
    repairability_score: float,
    renewable_energy_pct: float,
    worker_safety_incidents: int,
    iot_benchmark: str,
) -> str:
    """Return a GS1-conformant ProductionRecord XML string."""
    return f"""<ProductionRecord>
  <product_id>{product_id}</product_id>
  <total_co2_kg_equiv>{total_co2_kg_equiv}</total_co2_kg_equiv>
  <recycled_content_pct>{recycled_content_pct}</recycled_content_pct>
  <repairability_score>{repairability_score}</repairability_score>
  <renewable_energy_pct>{renewable_energy_pct}</renewable_energy_pct>
  <worker_safety_incidents>{worker_safety_incidents}</worker_safety_incidents>
  <iot_benchmark>{iot_benchmark}</iot_benchmark>
</ProductionRecord>"""
