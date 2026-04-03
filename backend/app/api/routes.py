from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
import json

from dotenv import load_dotenv
load_dotenv(override=True)

from app.services.lex_rules import (
    lexexplain_from_dataset,
    extract_case_id,
    ensure_list,
    ds_get,
    find_by_case_id,
    find_all_by_case_id,
    classify_evidence,
    map_conditions_to_risks,
)

# Minimal in-memory per conversation store (Python 3.8-safe typing)
DATASET_STORE: Dict[int, Dict[str, Any]] = {}

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str
    mode: str = "lex"  # "lex" | "normal"


def _conv_id(req: ChatRequest) -> int:
    return req.conversation_id or 1


def _intent(message: str) -> str:
    m = (message or "").lower()
    if "statute" in m:
        return "statute"
    if "risk" in m:
        return "risk"
    return "explain"


@router.post("/lexexplain/upload")
async def upload(files: List[UploadFile] = File(...)):
    conv_id = 1
    ds = DATASET_STORE.setdefault(conv_id, {})

    uploaded = []
    for f in files:
        raw = await f.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            continue

        key = (f.filename or "").lower().replace("-", "_").replace(" ", "_")
        key = key.replace(".json", "")
        ds[key] = data
        uploaded.append(f.filename)

    return {"ok": True, "conversation_id": conv_id, "uploaded": uploaded}


@router.post("/chat")
async def chat(req: ChatRequest):
    conv_id = _conv_id(req)
    ds = DATASET_STORE.setdefault(conv_id, {})

    # 1) NORMAL MODE: Groq (OpenAI-compatible) using your existing .env vars
    if (req.mode or "").lower() == "normal":
        try:
            import os
            import requests

            api_key = os.getenv("LLM_API_KEY")
            base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
            model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

            if not api_key:
                return {"conversation_id": conv_id, "assistant": "LLM_API_KEY missing in backend/.env"}

            url = base_url.rstrip("/") + "/chat/completions"

            r = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful AI assistant. Answer naturally."},
                        {"role": "user", "content": req.message},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 800,
                },
                timeout=60,
            )

            if r.status_code != 200:
                return {"conversation_id": conv_id, "assistant": f"Groq error {r.status_code}: {r.text}"}

            data = r.json()
            assistant = data["choices"][0]["message"]["content"]
            return {"conversation_id": conv_id, "assistant": assistant}

        except ImportError:
            return {"conversation_id": conv_id, "assistant": "Install packages: pip install requests python-dotenv"}
        except Exception as e:
            return {"conversation_id": conv_id, "assistant": f"Normal mode error: {str(e)}"}

    # 2) LEX MODE: branch by intent so buttons differ
    intent = _intent(req.message)

    if intent == "statute":
        cid = extract_case_id(req.message)
        cases = ensure_list(ds_get(ds, "cases"))
        orders = ensure_list(ds_get(ds, "bail_orders"))
        statutes = ensure_list(ds_get(ds, "statutes"))

        if not cid:
            cid = (cases[0].get("case_id") if cases and isinstance(cases[0], dict) else None) or (
                orders[0].get("case_id") if orders and isinstance(orders[0], dict) else None
            )

        if not cid:
            assistant = "I couldn't detect a case_id. Ask: 'Statute details for case C-IND-2024-001'."
        else:
            case_obj = find_by_case_id(cases, cid) or {}
            offences = ensure_list(case_obj.get("offences"))

            assistant = "## LexExplain — Statute Details (neutral, educational)\n\n"
            assistant += "### Boundary compliance\n- No legal advice, no outcome prediction, no guilt/innocence assessment.\n\n"
            assistant += f"### Case selected: {cid}\n"
            assistant += "### Offences listed\n" + (
                "\n".join([f"- {o}" for o in offences]) if offences else "- (none found)"
            ) + "\n\n"
            assistant += "### Statute dataset coverage\n"
            assistant += f"- Statute records available: {len(statutes)}\n" if statutes else "- No statutes.json uploaded (or key mismatch).\n"

    elif intent == "risk":
        cid = extract_case_id(req.message)
        cases = ensure_list(ds_get(ds, "cases"))
        orders = ensure_list(ds_get(ds, "bail_orders"))
        evidence = ensure_list(ds_get(ds, "evidence"))

        if not cid:
            cid = (cases[0].get("case_id") if cases and isinstance(cases[0], dict) else None) or (
                orders[0].get("case_id") if orders and isinstance(orders[0], dict) else None
            )

        if not cid:
            assistant = "I couldn't detect a case_id. Ask: 'Risk factors for case C-IND-2024-001'."
        else:
            order_obj = find_by_case_id(orders, cid) or {}
            reasoning_blocks = ensure_list(order_obj.get("reasoning_blocks"))
            conditions = ensure_list(order_obj.get("conditions"))

            rb_text = " ".join([str(x).lower() for x in reasoning_blocks])
            risks = []
            if "flight" in rb_text or "abscond" in rb_text:
                risks.append("Absconding / non-appearance risk")
            if "tamper" in rb_text or "witness" in rb_text:
                risks.append("Witness influence / evidence tampering risk")
            if "repeat" in rb_text or "reoffend" in rb_text:
                risks.append("Repeat offence risk")
            if not risks:
                risks = ["Typical risks: absconding, tampering, repeat offence (not confirmed in your data)."]

            ev_items = find_all_by_case_id(evidence, cid) if evidence else []
            ev_cls = classify_evidence(ev_items)

            assistant = "## LexExplain — Risk Factors (neutral, rule-based)\n\n"
            assistant += "### Risks\n" + "\n".join([f"- {r}" for r in risks]) + "\n\n"
            assistant += "### Mitigation via conditions\n"
            assistant += (
                "\n".join(map_conditions_to_risks(conditions, risks)) if conditions else "- (no conditions found)"
            ) + "\n\n"
            assistant += "### Evidence mix (context, not proof)\n"
            assistant += (
                f"- Oral: {len(ev_cls['oral'])}, Documentary: {len(ev_cls['documentary'])}, "
                f"Material: {len(ev_cls['material'])}, Unclear: {len(ev_cls['unknown'])}\n"
            )

    else:
        assistant = lexexplain_from_dataset(ds, req.message)

    return {"conversation_id": conv_id, "assistant": assistant}
