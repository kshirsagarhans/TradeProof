"""
TradeProof Reconciliation Engine
Executes all 7 validation checks between BL and SBs.
"""
import uuid
from datetime import datetime
from utils.helpers import normalize_string, fuzzy_match, normalize_weight, parse_date_normalize
from models.bill_of_lading import BillOfLading, ContainerInfo
from models.shipping_bill import ShippingBill
from models.reconciliation import ReconciliationCheck, ReconciliationReport
from config import (
    FUZZY_MATCH_THRESHOLD, HS_DESCRIPTION_THRESHOLD,
    WEIGHT_TOLERANCE_PCT, STATUS_MATCH, STATUS_MISMATCH,
    STATUS_MISSING, STATUS_WARNING
)

def _check(id, name, category, status, severity, bl_val, sb_val, details, sub_checks=None):
    return ReconciliationCheck(
        check_id=id, check_name=name, category=category,
        status=status, severity=severity, bl_value=bl_val,
        sb_value=sb_val, details=details,
        sub_checks=sub_checks or []
    )

# ── CHECK 1: Identifier Match ─────────────────────────────────────────────────
def check_identifiers(bl: BillOfLading, sbs: list[ShippingBill]) -> list[ReconciliationCheck]:
    results = []
    sb_ref = sbs[0] if sbs else None  # Use first SB for identifier comparison

    fields = [
        ("IDENT-01", "Exporter Name", "IDENTIFIERS",
         bl.exporter_name, sb_ref.exporter_name if sb_ref else None),
        ("IDENT-02", "Exporter Address", "IDENTIFIERS",
         bl.exporter_address, sb_ref.exporter_address if sb_ref else None),
        ("IDENT-03", "Consignee Name", "IDENTIFIERS",
         bl.consignee_name, sb_ref.consignee_name if sb_ref else None),
        ("IDENT-04", "Consignee Address", "IDENTIFIERS",
         bl.consignee_address, sb_ref.consignee_address if sb_ref else None),
        ("IDENT-05", "Port of Loading", "IDENTIFIERS",
         bl.port_of_loading, sb_ref.port_of_loading if sb_ref else None),
        ("IDENT-06", "Port of Discharge", "IDENTIFIERS",
         bl.port_of_discharge, sb_ref.port_of_discharge if sb_ref else None),
        ("IDENT-07", "Port of Final Destination", "IDENTIFIERS",
         bl.port_of_final_destination, sb_ref.port_of_final_destination if sb_ref else None),
    ]

    severity_map = {
        "Exporter Name": "HIGH", "Consignee Name": "HIGH",
        "Port of Loading": "HIGH", "Port of Discharge": "HIGH",
        "Exporter Address": "MEDIUM", "Consignee Address": "MEDIUM",
        "Port of Final Destination": "MEDIUM"
    }

    for check_id, field_name, category, bl_val, sb_val in fields:
        if not sb_ref:
            results.append(_check(check_id, field_name, category,
                STATUS_MISSING, "HIGH", bl_val, None,
                "No Shipping Bill available for comparison"))
            continue

        if not bl_val and not sb_val:
            results.append(_check(check_id, field_name, category,
                STATUS_MISSING, severity_map.get(field_name, "MEDIUM"),
                bl_val, sb_val, "Field absent in both documents"))
        elif not bl_val or not sb_val:
            results.append(_check(check_id, field_name, category,
                STATUS_MISSING, severity_map.get(field_name, "HIGH"),
                bl_val, sb_val, "Field missing in one document"))
        else:
            is_match, ratio = fuzzy_match(bl_val, sb_val, FUZZY_MATCH_THRESHOLD)
            if is_match:
                results.append(_check(check_id, field_name, category,
                    STATUS_MATCH, severity_map.get(field_name, "MEDIUM"),
                    bl_val, sb_val, f"Match confirmed (similarity: {ratio:.0%})"))
            else:
                results.append(_check(check_id, field_name, category,
                    STATUS_MISMATCH, severity_map.get(field_name, "HIGH"),
                    bl_val, sb_val, f"Values differ (similarity: {ratio:.0%})"))

    return results


# ── CHECK 2: SB Number & Date Pairing ────────────────────────────────────────
def check_sb_documentation(bl: BillOfLading, sbs: list[ShippingBill]) -> list[ReconciliationCheck]:
    results = []
    bl_sb_refs = bl.shipping_bill_references or []

    if not bl_sb_refs:
        results.append(_check("DOC-01", "SB Reference in BL", "DOCUMENTATION",
            STATUS_MISSING, "HIGH", None, None,
            "No Shipping Bill references found in the Bill of Lading"))
        return results

    # Build SB lookup from uploaded SBs
    sb_lookup = {normalize_string(sb.sb_number): sb for sb in sbs}

    for i, ref in enumerate(bl_sb_refs, 1):
        ref_num = normalize_string(ref.get("sb_number", ""))
        ref_date = parse_date_normalize(ref.get("sb_date", ""))
        check_id = f"DOC-{i:02d}"

        if ref_num not in sb_lookup:
            results.append(_check(check_id, f"SB {ref_num} — Not Found",
                "DOCUMENTATION", STATUS_MISSING, "HIGH",
                f"{ref_num} / {ref_date}", None,
                f"SB '{ref_num}' referenced in BL was not uploaded for comparison"))
        else:
            matched_sb = sb_lookup[ref_num]
            actual_date = parse_date_normalize(matched_sb.sb_date)
            if ref_date == actual_date or (not ref_date and not actual_date):
                results.append(_check(check_id, f"SB {ref_num} — Number & Date",
                    "DOCUMENTATION", STATUS_MATCH, "HIGH",
                    f"{ref_num} / {ref_date}", f"{matched_sb.sb_number} / {actual_date}",
                    "SB number and date match confirmed"))
            elif ref_date == actual_date:
                results.append(_check(check_id, f"SB {ref_num} — Number Match",
                    "DOCUMENTATION", STATUS_MATCH, "MEDIUM",
                    f"{ref_num} / {ref_date}", f"{matched_sb.sb_number} / {actual_date}",
                    "SB number matches; date field absent in BL reference"))
            else:
                results.append(_check(check_id, f"SB {ref_num} — Date Mismatch",
                    "DOCUMENTATION", STATUS_MISMATCH, "HIGH",
                    f"{ref_num} / {ref_date}", f"{matched_sb.sb_number} / {actual_date}",
                    f"SB number matches but date differs: BL shows '{ref_date}', SB shows '{actual_date}'"))

    return results


# ── CHECK 3: Package Count Aggregation ───────────────────────────────────────
def check_package_count(bl: BillOfLading, sbs: list[ShippingBill]) -> ReconciliationCheck:
    bl_pkg = bl.total_packages
    sb_totals = [sb.pkg_total for sb in sbs if sb.pkg_total is not None]
    sb_sum = sum(sb_totals) if sb_totals else None
    breakdown = ", ".join([f"{sbs[i].sb_number}: {sbs[i].pkg_total}" for i in range(len(sbs)) if sbs[i].pkg_total])

    if bl_pkg is None:
        return _check("QTY-01", "Package Count — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_MISSING, "HIGH", None, sb_sum,
            "Package count absent in Bill of Lading")
    if sb_sum is None:
        return _check("QTY-01", "Package Count — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_MISSING, "HIGH", bl_pkg, None,
            "No package counts extracted from Shipping Bills")

    delta = sb_sum - bl_pkg
    if delta == 0:
        return _check("QTY-01", "Package Count — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_MATCH, "HIGH", bl_pkg, f"{sb_sum} (Σ: {breakdown})",
            f"Package counts match: {bl_pkg}")
    elif abs(delta) <= 1:
        return _check("QTY-01", "Package Count — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_WARNING, "MEDIUM", bl_pkg, f"{sb_sum} (Σ: {breakdown})",
            f"Minor discrepancy: BL={bl_pkg}, SBs Σ={sb_sum}, Delta={delta:+d}")
    else:
        return _check("QTY-01", "Package Count — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_MISMATCH, "HIGH", bl_pkg, f"{sb_sum} (Σ: {breakdown})",
            f"Package count mismatch: BL={bl_pkg}, SBs Σ={sb_sum}, Delta={delta:+d}")


# ── CHECK 4: Gross Weight Aggregation ────────────────────────────────────────
def check_gross_weight(bl: BillOfLading, sbs: list[ShippingBill]) -> ReconciliationCheck:
    bl_wt = bl.gross_weight
    bl_unit = bl.gross_weight_unit or "KG"

    if bl_wt is None:
        return _check("QTY-02", "Gross Weight — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_MISSING, "HIGH", None, None,
            "Gross weight absent in Bill of Lading")

    bl_wt_kg = normalize_weight(bl_wt, bl_unit)
    sb_items = [(sb.gross_weight_total, sb.gross_weight_unit or "KG", sb.sb_number)
                for sb in sbs if sb.gross_weight_total is not None]

    if not sb_items:
        return _check("QTY-02", "Gross Weight — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_MISSING, "HIGH", f"{bl_wt} {bl_unit}", None,
            "No gross weight extracted from Shipping Bills")

    sb_sum_kg = sum(normalize_weight(v, u) for v, u, _ in sb_items)
    breakdown = ", ".join([f"{n}: {v} {u}" for v, u, n in sb_items])
    tolerance = bl_wt_kg * WEIGHT_TOLERANCE_PCT
    delta_kg = sb_sum_kg - bl_wt_kg

    if abs(delta_kg) <= tolerance:
        return _check("QTY-02", "Gross Weight — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_MATCH, "HIGH", f"{bl_wt} {bl_unit}", f"{sb_sum_kg:.2f} KG (Σ: {breakdown})",
            f"Weights match within tolerance. BL={bl_wt_kg:.2f} KG, SBs Σ={sb_sum_kg:.2f} KG, Δ={delta_kg:+.2f} KG")
    else:
        return _check("QTY-02", "Gross Weight — BL vs Σ SBs", "QUANTITATIVE",
            STATUS_MISMATCH, "HIGH", f"{bl_wt} {bl_unit}", f"{sb_sum_kg:.2f} KG (Σ: {breakdown})",
            f"Weight mismatch: BL={bl_wt_kg:.2f} KG, SBs Σ={sb_sum_kg:.2f} KG, Δ={delta_kg:+.2f} KG")


# ── CHECK 5: Container & Seal Verification ───────────────────────────────────
def check_containers(bl: BillOfLading, sbs: list[ShippingBill]) -> list[ReconciliationCheck]:
    results = []

    bl_containers = {
        normalize_string(c.container_number): normalize_string(c.seal_number)
        for c in bl.containers if c.container_number
    }
    sb_containers = {}
    for sb in sbs:
        for c in sb.containers:
            if c.container_number:
                sb_containers[normalize_string(c.container_number)] = {
                    "seal": normalize_string(c.seal_number),
                    "sb": sb.sb_number
                }

    if not bl_containers and not sb_containers:
        return [_check("LOG-00", "Container Verification", "LOGISTICS",
            STATUS_MISSING, "HIGH", None, None,
            "No container data found in BL or SBs")]

    # Containers in BL but not in SBs
    for cnum, seal in bl_containers.items():
        check_id = f"LOG-{cnum[:8]}"
        if cnum not in sb_containers:
            results.append(_check(check_id, f"Container {cnum}", "LOGISTICS",
                STATUS_MISSING, "HIGH", f"{cnum} / Seal: {seal}", None,
                f"Container {cnum} found in BL but NOT in any Shipping Bill"))
        else:
            sb_seal = sb_containers[cnum]["seal"]
            sb_name = sb_containers[cnum]["sb"]
            if seal == sb_seal:
                results.append(_check(check_id, f"Container {cnum}", "LOGISTICS",
                    STATUS_MATCH, "LOW", f"{cnum} / Seal: {seal}",
                    f"{cnum} / Seal: {sb_seal} (SB: {sb_name})",
                    f"Container and seal match (found in {sb_name})"))
            else:
                results.append(_check(check_id, f"Container {cnum} — Seal Mismatch", "LOGISTICS",
                    STATUS_MISMATCH, "HIGH", f"{cnum} / Seal: {seal}",
                    f"{cnum} / Seal: {sb_seal} (SB: {sb_name})",
                    f"Container matches but SEAL DIFFERS: BL has '{seal}', SB has '{sb_seal}'"))

    # Containers in SBs but not in BL
    for cnum, info in sb_containers.items():
        if cnum not in bl_containers:
            check_id = f"LOG-X{cnum[:6]}"
            results.append(_check(check_id, f"Container {cnum} — Extra in SB", "LOGISTICS",
                STATUS_WARNING, "MEDIUM", None,
                f"{cnum} / Seal: {info['seal']} (SB: {info['sb']})",
                f"Container {cnum} found in SB '{info['sb']}' but NOT in Bill of Lading"))

    if not results:
        results.append(_check("LOG-ALL", "Container & Seal Verification", "LOGISTICS",
            STATUS_MATCH, "LOW", f"{len(bl_containers)} containers", f"{len(sb_containers)} containers",
            f"All {len(bl_containers)} containers and seals reconciled successfully"))

    return results


# ── CHECK 6: HS Code & Description ───────────────────────────────────────────
def check_hs_classification(bl: BillOfLading, sbs: list[ShippingBill]) -> list[ReconciliationCheck]:
    results = []
    for i, sb in enumerate(sbs, 1):
        check_id = f"CLASS-{i:02d}"
        bl_hs = normalize_string(bl.hs_code or "")
        sb_hs = normalize_string(sb.hs_code or "")
        bl_desc = normalize_string(bl.hs_description or "")
        sb_desc = normalize_string(sb.hs_description or "")

        if not bl_hs and not sb_hs:
            results.append(_check(check_id, f"HS Code — BL vs {sb.sb_number}", "CLASSIFICATION",
                STATUS_MISSING, "MEDIUM", None, None,
                "HS Code absent in both documents"))
            continue

        code_match = bl_hs == sb_hs
        desc_match, desc_ratio = fuzzy_match(bl_desc, sb_desc, HS_DESCRIPTION_THRESHOLD)

        if code_match and desc_match:
            results.append(_check(check_id, f"HS Code & Desc — BL vs {sb.sb_number}", "CLASSIFICATION",
                STATUS_MATCH, "LOW", f"{bl_hs}: {bl_desc}", f"{sb_hs}: {sb_desc}",
                f"HS Code and description match (desc similarity: {desc_ratio:.0%})"))
        elif code_match and not desc_match:
            results.append(_check(check_id, f"HS Description Mismatch — {sb.sb_number}", "CLASSIFICATION",
                STATUS_WARNING, "MEDIUM", f"{bl_hs}: {bl_desc}", f"{sb_hs}: {sb_desc}",
                f"HS Code matches but descriptions differ (similarity: {desc_ratio:.0%})"))
        elif not code_match:
            results.append(_check(check_id, f"HS Code Mismatch — {sb.sb_number}", "CLASSIFICATION",
                STATUS_MISMATCH, "HIGH", f"{bl_hs}: {bl_desc}", f"{sb_hs}: {sb_desc}",
                f"HS Code mismatch: BL='{bl_hs}', SB='{sb_hs}'"))

    return results


# ── CHECK 7: Invoice Reconciliation ──────────────────────────────────────────
def check_invoices(bl: BillOfLading, sbs: list[ShippingBill]) -> list[ReconciliationCheck]:
    results = []

    if not bl.invoice_number and not bl.invoice_amount:
        results.append(_check("FIN-00", "Invoice Reconciliation", "FINANCIAL",
            STATUS_MISSING, "LOW", None, None,
            "No invoice information present in Bill of Lading — check skipped"))
        return results

    for i, sb in enumerate(sbs, 1):
        check_id_num = f"FIN-NUM-{i:02d}"
        check_id_amt = f"FIN-AMT-{i:02d}"

        # Invoice number
        if bl.invoice_number:
            is_match, ratio = fuzzy_match(bl.invoice_number, sb.invoice_number or "")
            if not sb.invoice_number:
                results.append(_check(check_id_num, f"Invoice No. — BL vs {sb.sb_number}", "FINANCIAL",
                    STATUS_MISSING, "MEDIUM", bl.invoice_number, None,
                    f"Invoice number absent in SB '{sb.sb_number}'"))
            elif is_match:
                results.append(_check(check_id_num, f"Invoice No. — BL vs {sb.sb_number}", "FINANCIAL",
                    STATUS_MATCH, "MEDIUM", bl.invoice_number, sb.invoice_number,
                    "Invoice numbers match"))
            else:
                results.append(_check(check_id_num, f"Invoice No. — BL vs {sb.sb_number}", "FINANCIAL",
                    STATUS_MISMATCH, "HIGH", bl.invoice_number, sb.invoice_number,
                    f"Invoice number mismatch (similarity: {ratio:.0%})"))

        # Invoice amount
        if bl.invoice_amount is not None and sb.invoice_amount is not None:
            delta = abs(bl.invoice_amount - sb.invoice_amount)
            if delta < 0.01:
                results.append(_check(check_id_amt, f"Invoice Amt — BL vs {sb.sb_number}", "FINANCIAL",
                    STATUS_MATCH, "HIGH", f"{bl.invoice_currency} {bl.invoice_amount:.2f}",
                    f"{sb.invoice_currency} {sb.invoice_amount:.2f}", "Invoice amounts match"))
            else:
                results.append(_check(check_id_amt, f"Invoice Amt — BL vs {sb.sb_number}", "FINANCIAL",
                    STATUS_MISMATCH, "HIGH", f"{bl.invoice_currency} {bl.invoice_amount:.2f}",
                    f"{sb.invoice_currency} {sb.invoice_amount:.2f}",
                    f"Amount mismatch: Δ = {delta:.2f}"))

    return results


# ── CHECK 8: Physical Verification ──────────────────────────────────────────
def check_physical_seals(bl: BillOfLading, sbs: list[ShippingBill], seal_data: dict) -> list[ReconciliationCheck]:
    results = []
    if not seal_data or "containers" not in seal_data or not seal_data["containers"]:
        return results
        
    physical_containers = seal_data["containers"]
    
    bl_containers = {
        normalize_string(c.container_number): normalize_string(c.seal_number)
        for c in bl.containers if c.container_number
    }
    
    sb_containers = {}
    for sb in sbs:
        for c in sb.containers:
            if c.container_number:
                sb_containers[normalize_string(c.container_number)] = normalize_string(c.seal_number)

    for i, p_cont in enumerate(physical_containers, 1):
        p_cnum = normalize_string(p_cont.get("container_number", ""))
        p_seal = normalize_string(p_cont.get("seal_number", ""))
        check_id = f"PHYS-{i:02d}"
        
        if not p_cnum or not p_seal:
            continue
            
        bl_seal = bl_containers.get(p_cnum)
        sb_seal = sb_containers.get(p_cnum)
        
        if not bl_seal and not sb_seal:
            results.append(_check(check_id, f"Physical Container {p_cnum}", "PHYSICAL VERIFICATION",
                STATUS_WARNING, "HIGH", None, None,
                f"Physical container '{p_cnum}' (Seal: {p_seal}) was not found in any digital document."))
            continue
            
        if bl_seal:
            if bl_seal == p_seal:
                results.append(_check(f"{check_id}-BL", f"Physical Seal vs BL ({p_cnum})", "PHYSICAL VERIFICATION",
                    STATUS_MATCH, "HIGH", f"BL: {bl_seal}", f"Physical: {p_seal}",
                    "Physical seal matches Bill of Lading."))
            else:
                results.append(_check(f"{check_id}-BL", f"Physical Seal vs BL ({p_cnum})", "PHYSICAL VERIFICATION",
                    STATUS_MISMATCH, "HIGH", f"BL: {bl_seal}", f"Physical: {p_seal}",
                    "TAMPER WARNING: Physical seal does NOT match Bill of Lading."))
                    
        if sb_seal:
            if sb_seal == p_seal:
                results.append(_check(f"{check_id}-SB", f"Physical Seal vs SB ({p_cnum})", "PHYSICAL VERIFICATION",
                    STATUS_MATCH, "HIGH", f"SB: {sb_seal}", f"Physical: {p_seal}",
                    "Physical seal matches Shipping Bill."))
            else:
                results.append(_check(f"{check_id}-SB", f"Physical Seal vs SB ({p_cnum})", "PHYSICAL VERIFICATION",
                    STATUS_MISMATCH, "HIGH", f"SB: {sb_seal}", f"Physical: {p_seal}",
                    "TAMPER WARNING: Physical seal does NOT match Shipping Bill."))

    return results


# ── MASTER RECONCILE FUNCTION ─────────────────────────────────────────────────
def run_full_reconciliation(bl_data: dict, sb_data_list: list[dict], seal_data: dict = None) -> ReconciliationReport:
    """Run all checks including physical verification, and return a full ReconciliationReport."""

    from models.bill_of_lading import BillOfLading, ContainerInfo
    from models.shipping_bill import ShippingBill

    # Deserialize
    bl = BillOfLading(**{k: v for k, v in bl_data.items() if k not in ("raw_text",)})
    bl.raw_text = bl_data.get("raw_text")

    sbs = []
    for sb_raw in sb_data_list:
        containers_raw = sb_raw.get("containers", [])
        containers = [ContainerInfo(**c) for c in containers_raw]
        sb = ShippingBill(**{k: v for k, v in sb_raw.items() if k not in ("raw_text", "containers")})
        sb.containers = containers
        sb.raw_text = sb_raw.get("raw_text")
        sbs.append(sb)

    all_checks = []
    all_checks.extend(check_identifiers(bl, sbs))
    all_checks.extend(check_sb_documentation(bl, sbs))
    all_checks.append(check_package_count(bl, sbs))
    all_checks.append(check_gross_weight(bl, sbs))
    all_checks.extend(check_containers(bl, sbs))
    all_checks.extend(check_hs_classification(bl, sbs))
    all_checks.extend(check_invoices(bl, sbs))
    
    if seal_data:
        all_checks.extend(check_physical_seals(bl, sbs, seal_data))

    report = ReconciliationReport(
        report_id=str(uuid.uuid4())[:8].upper(),
        generated_at=datetime.now().strftime("%d %b %Y, %H:%M:%S"),
        bl_number=bl.bl_number or "UNKNOWN",
        sb_count=len(sbs),
        total_checks=0,
        match_count=0,
        mismatch_count=0,
        missing_count=0,
        warning_count=0,
        match_rate_pct=0.0,
        port_of_loading_lat=bl.port_of_loading_lat,
        port_of_loading_lon=bl.port_of_loading_lon,
        port_of_discharge_lat=bl.port_of_discharge_lat,
        port_of_discharge_lon=bl.port_of_discharge_lon,
        checks=all_checks,
        summary=""
    )
    
    report.update_metrics()
    return report
