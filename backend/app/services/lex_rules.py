import json
import re
from typing import Any

BOUNDARY_REFUSAL = (
    "I can’t provide legal advice, predict outcomes, or assess guilt/innocence. "
    "I can explain bail reasoning in a neutral, rule-based way from the uploaded bail-order data."
)

def is_boundary_violation(user_text: str) -> bool:
    t = user_text.lower()
    triggers = [
        "will i get bail", "will he get bail", "will she get bail", "chance of bail",
        "predict", "prediction", "what will judge do", "what will court do",
        "how to win bail", "how to get bail", "tell me what to say in court",
        "is he guilty", "is she guilty", "prove guilty", "prove innocent",
        "legal advice", "should i file", "what should i do",
    ]
    return any(x in t for x in triggers)

def extract_case_id(text: str) -> str | None:
    # Matches: C-IND-2024-001 (your sample)
    m = re.search(r"\bC-[A-Z]{3}-\d{4}-\d{3}\b", text.upper())
    return m.group(0) if m else None

def ensure_list(x: Any) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]

def classify_evidence(e_items: list[dict] | list[str] | Any) -> dict:
    out = {"oral": [], "documentary": [], "material": [], "unknown": []}
    items = ensure_list(e_items)
    for it in items:
        s = json.dumps(it).lower() if not isinstance(it, str) else it.lower()
        if any(k in s for k in ["witness", "statement", "oral", "testimony", "complainant"]):
            out["oral"].append(it)
        elif any(k in s for k in ["document", "record", "report", "medical", "forensic", "cctv", "cdr", "bank"]):
            out["documentary"].append(it)
        elif any(k in s for k in ["weapon", "seizure", "recovery", "material", "object", "mobile"]):
            out["material"].append(it)
        else:
            out["unknown"].append(it)
    return out

def normalize_key(filename_key: str) -> str:
    return (filename_key or "").lower().strip().replace("-", "_").replace(" ", "_")

def ds_get(dataset: dict[str, Any], key: str) -> Any:
    return dataset.get(normalize_key(key))

def find_by_case_id(items: Any, case_id: str) -> dict | None:
    for obj in ensure_list(items):
        if isinstance(obj, dict) and obj.get("case_id") == case_id:
            return obj
    return None

def find_all_by_case_id(items: Any, case_id: str) -> list[dict]:
    out = []
    for obj in ensure_list(items):
        if isinstance(obj, dict) and obj.get("case_id") == case_id:
            out.append(obj)
    return out

def map_conditions_to_risks(conditions: list[str], risks: list[str]) -> list[str]:
    # simple, explainable mapping (rule-based)
    joined = []
    for c in conditions:
        c_low = c.lower()
        tags = []
        if any(k in c_low for k in ["report", "police", "attendance", "appear"]):
            tags.append("Ensures appearance (reduces absconding risk).")
        if any(k in c_low for k in ["no contact", "witness", "threat", "influence"]):
            tags.append("Reduces witness influence/tampering risk.")
        if any(k in c_low for k in ["travel", "passport", "leave jurisdiction"]):
            tags.append("Reduces flight risk.")
        if any(k in c_low for k in ["bond", "surety", "inr", "rs", "bail amount"]):
            tags.append("Creates compliance incentive.")
        if not tags and risks:
            tags.append("General mitigation measure tied to risk management.")
        joined.append(f"- {c} ({' '.join(tags)})")
    return joined

def neutralize_emotional(text: str) -> str:
    # Convert emotional narratives into neutral procedural framing
    # (No accusation about judge, no moral language)
    t = text.strip()
    patterns = [
        (r"\bcorrupt\b", "alleged procedural concern"),
        (r"\bbad judge\b", "concern about reasoning process"),
        (r"\bbiased\b", "concern about neutrality"),
        (r"\bunfair\b", "concern about consistency"),
        (r"\bmonster\b", "serious allegation"),
    ]
    for p, repl in patterns:
        t = re.sub(p, repl, t, flags=re.IGNORECASE)
    return t

def build_lex_explain(case: dict | None, order: dict | None, evidence_items: list[Any], user_query: str) -> str:
    q = neutralize_emotional(user_query)

    offences = ensure_list((case or {}).get("offences"))
    category = (case or {}).get("offence_category")
    max_years = (case or {}).get("max_punishment_years")
    investigation = (case or {}).get("investigation_status")
    days = (case or {}).get("days_in_custody")
    co_accused_present = (case or {}).get("co_accused_present")

    bail_status = (order or {}).get("bail_status")
    conditions = ensure_list((order or {}).get("conditions"))
    reasoning_blocks = ensure_list((order or {}).get("reasoning_blocks"))

    ev = classify_evidence(evidence_items)

    # Infer risks from reasoning blocks (rule-based, explainable)
    inferred_risks = []
    rb_text = " ".join([str(x).lower() for x in reasoning_blocks])
    if "flight" in rb_text or "abscond" in rb_text:
        inferred_risks.append("Absconding / non-appearance risk")
    if "tamper" in rb_text or "witness" in rb_text:
        inferred_risks.append("Witness influence / evidence tampering risk")
    if "repeat" in rb_text or "reoffend" in rb_text:
        inferred_risks.append("Repeat offence risk")
    if not inferred_risks and reasoning_blocks:
        inferred_risks.append("Risks referenced in the order’s reasoning blocks (as provided).")

    md = []
    md.append("## LexExplain — Bail Decision Justification (neutral, rule-based)")
    md.append("")
    md.append("### 0) Boundary compliance")
    md.append("- I cannot give legal advice, predict outcomes, or decide guilt/innocence.")
    md.append("- I can explain *how* bail reasoning is typically structured using the uploaded data.")
    md.append("")

    md.append("### 1) User question (neutralized)")
    md.append(f"- Query intent: {q}")
    md.append("")

    md.append("### 2) Charge → legal principle mapping (from uploaded case data)")
    if offences:
        md.append("- Alleged offences listed:")
        for o in offences:
            md.append(f"  - {o}")
    else:
        md.append("- Offences not found in the selected case record.")
    if category:
        md.append(f"- Offence category noted: {category}")
    if max_years is not None:
        md.append(f"- Max punishment (as provided): {max_years} years")
    md.append("- Principle frame: bail is treated as a procedural risk-management decision, not a finding on guilt.")
    md.append("")

    md.append("### 3) Risk assessment (what the court tries to prevent)")
    if inferred_risks:
        for r in inferred_risks:
            md.append(f"- Risk: {r}")
    else:
        md.append("- Risks not explicit in data; typical risks include absconding, tampering, and repeat offence.")
    if reasoning_blocks:
        md.append("- Reasoning blocks referenced in the uploaded bail order:")
        for rb in reasoning_blocks:
            md.append(f"  - {rb}")
    md.append("")

    md.append("### 4) Mitigation (how conditions reduce risks)")
    if conditions:
        md.extend(map_conditions_to_risks(conditions, inferred_risks))
    else:
        md.append("- No bail conditions found in uploaded order.")
    md.append("")

    md.append("### 5) Statutory limits / detention timeline (explainable)")
    if investigation:
        md.append(f"- Investigation status (as provided): {investigation}")
    if days is not None:
        md.append(f"- Days in custody (as provided): {days}")
    md.append("- Explanation: statutory timelines can affect continued detention and may trigger statutory/default bail rights depending on the governing law and filings (the exact trigger must be verified from the order/statute).")
    md.append("")

    md.append("### 6) Evidence classification (educational)")
    md.append(f"- Oral items: {len(ev['oral'])}")
    md.append(f"- Documentary items: {len(ev['documentary'])}")
    md.append(f"- Material items: {len(ev['material'])}")
    md.append(f"- Unclear items: {len(ev['unknown'])}")
    md.append("")

    md.append("### 7) Parity / co-accused fairness (if present)")
    if co_accused_present is True:
        md.append("- Co-accused present: yes; parity can be discussed by comparing roles and risks to ensure consistency.")
    elif co_accused_present is False:
        md.append("- Co-accused present: no parity issue indicated in the case record.")
    else:
        md.append("- Co-accused parity information not found in case record.")
    md.append("")

    md.append("### 8) Neutral justification summary (based on order status)")
    if bail_status:
        md.append(f"- Bail status in uploaded order: {bail_status}")
        md.append("- Neutral reading: the decision reflects how the court balanced identified risks with mitigating conditions and procedural posture.")
    else:
        md.append("- Bail status not found in uploaded order.")
    md.append("")

    md.append("### 9) Fail-safe compliance reminder")
    md.append("- If you ask for strategy/advice or predictions, I will refuse and continue only with neutral explanation.")
    return "\n".join(md)

def lexexplain_from_dataset(dataset: dict[str, Any], user_query: str) -> str:
    if is_boundary_violation(user_query):
        return BOUNDARY_REFUSAL

    cases = ds_get(dataset, "cases")
    bail_orders = ds_get(dataset, "bail_orders")
    evidence = ds_get(dataset, "evidence")

    case_list = ensure_list(cases)
    order_list = ensure_list(bail_orders)
    evidence_list = ensure_list(evidence)

    if not case_list and not order_list:
        return "No usable case/order data found. Please upload cases.json and bail_orders.json."

    # pick case_id
    cid = extract_case_id(user_query)
    if not cid:
        # default to first case_id we can find
        cid = (case_list[0].get("case_id") if case_list and isinstance(case_list[0], dict) else None) or (
            order_list[0].get("case_id") if order_list and isinstance(order_list[0], dict) else None
        )

    if not cid:
        return "I couldn't detect a case_id. Please ask like: 'Explain bail for case C-IND-2024-001'."

    case_obj = find_by_case_id(case_list, cid)
    order_obj = find_by_case_id(order_list, cid)
    ev_items = find_all_by_case_id(evidence_list, cid) if evidence_list else []

    return build_lex_explain(case_obj, order_obj, ev_items, user_query)
