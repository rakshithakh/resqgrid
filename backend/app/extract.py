"""Turns a message into structured data, with Gemini if a key is set or a keyword extractor otherwise.

Both return the same schema. The model is never asked for coordinates or routes.
"""

from __future__ import annotations
import os
import re
import json
from typing import Literal
from pydantic import BaseModel, Field

TYPES = ["water", "food", "medical", "rescue", "shelter", "other"]


class Extraction(BaseModel):
    need_types: list[Literal["water", "food", "medical", "rescue", "shelter", "other"]] = Field(
        default_factory=list
    )
    people: int = Field(default=0, ge=0, le=100000)
    vulnerable: list[str] = Field(default_factory=list)
    urgency: Literal["low", "medium", "high", "critical"] = "medium"
    language: str = "en"
    confidence: float = Field(default=0.4, ge=0, le=1)
    source: str = "rules"


KW = {
    "rescue": [
        "stuck",
        "trapped",
        "stranded",
        "roof",
        "rooftop",
        "chhat",
        "fase",
        "fans",
        "rescue",
        "boat",
        "drowning",
        "bachao",
        "सिलुक",
        "छत",
        "फंस",
        "फसे",
        "बचाओ",
        "ಸಿಲುಕಿ",
        "ರಕ್ಷಣೆ",
        "ಬೋಟ್",
    ],
    "medical": [
        "medicine",
        "medical",
        "doctor",
        "injured",
        "ambulance",
        "insulin",
        "dawai",
        "dawa",
        "davai",
        "patient",
        "dengue",
        "malaria",
        "fever",
        "cholera",
        "diarrhoea",
        "diarrhea",
        "typhoid",
        "sick",
        "illness",
        "disease",
        "infection",
        "vomiting",
        "snake",
        "bukhar",
        "बुखार",
        "बीमार",
        "ಜ್ವರ",
        "दवा",
        "दवाई",
        "घायल",
        "ಔಷಧ",
        "ಗಾಯ",
        "ಆಂಬ್ಯುಲೆನ್ಸ್",
    ],
    "water": ["water", "paani", "pani", "neeru", "पानी", "ನೀರು"],
    "food": ["food", "khana", "ration", "oota", "aahara", "hungry", "bhookh", "खाना", "भोजन", "ಆಹಾರ", "ಊಟ"],
    "shelter": ["shelter", "blanket", "blankets", "tent", "camp", "aashray", "आश्रय", "कंबल", "ಆಶ್ರಯ", "ಕಂಬಳಿ"],
}
VUL = {
    "children": ["child", "children", "kids", "baby", "bachche", "bachchon", "बच्चे", "बच्चों", "ಮಕ್ಕಳು"],
    "elderly": ["elderly", "old age", "senior", "bujurg", "बुजुर्ग", "ವಯಸ್ಸಾದ", "bedridden"],
    "pregnant": ["pregnant", "garbhini", "गर्भवती", "ಗರ್ಭಿಣಿ"],
    "injured": ["injured", "ghayal", "घायल", "ಗಾಯ", "diabetic", "insulin"],
}
URGENT = [
    "urgent",
    "emergency",
    "jaldi",
    "turant",
    "immediately",
    "asap",
    "drowning",
    "bachao",
    "जल्दी",
    "तुरंत",
    "बचाओ",
]
HI_LAT = {
    "mein",
    "hai",
    "hain",
    "chahiye",
    "log",
    "paani",
    "fase",
    "ke",
    "ko",
    "nahi",
    "bahut",
    "dawai",
    "khana",
    "chhat",
    "bachche",
}
KN_LAT = {"neeru", "beku", "illa", "ide", "maneyalli", "jana", "madi", "aahara", "oota"}


def _has(t, w):
    return re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", t) if w.isascii() else (w in t)


def detect_lang(text):
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & HI_LAT) >= 2:
        return "hi-Latn"
    if len(words & KN_LAT) >= 1:
        return "kn-Latn"
    return "en"


def rules_extract(text: str) -> Extraction:
    t = text.lower()
    types = [k for k, ws in KW.items() if any(_has(t, w) for w in ws)]
    people = 0
    m = re.search(
        r"(\d{1,5})\s*(?:log|logo|people|persons?|members|families|family|residents|ppl|workers|patients|जन|लोग|लोगों|ಜನ|ಜನರು|ಮಂದಿ)",
        t,
    )
    if not m:
        m = re.search(r"(?:around|about|approx\.?|nearly)\s*(\d{1,5})", t)
    if not m:
        s = re.sub(r"(?:ward|wd|वार्ड|ವಾರ್ಡ್)\s*(?:no\.?|number)?\s*[-#:]?\s*\d+", " ", t)
        m = re.search(r"\b(\d{1,5})\b", s)
    if m:
        people = int(m.group(1))
        if re.search(r"famil", m.group(0)):
            people *= 4
    vul = [k for k, ws in VUL.items() if any(_has(t, w) for w in ws)]
    rescue = "rescue" in types
    if any(_has(t, w) for w in URGENT) or (rescue and (people >= 20 or vul)):
        urg = "critical"
    elif rescue or "medical" in types:
        urg = "high"
    else:
        urg = "medium"
    conf = 0.4 + (0.2 if types else 0) + (0.2 if people else 0)
    return Extraction(
        need_types=types or ["other"],
        people=people,
        vulnerable=vul,
        urgency=urg,
        language=detect_lang(text),
        confidence=min(conf, 0.8),
        source="rules",
    )


PROMPT = """You extract relief requests from flood-emergency messages in English, Hindi, Kannada or romanised mixes.
Return ONLY JSON: {"need_types":[water|food|medical|rescue|shelter|other], "people":int (0 if unknown),
"vulnerable":[children|elderly|pregnant|injured], "urgency":"low|medium|high|critical",
"language":"en|hi|kn|hi-Latn|kn-Latn", "confidence":0..1}.
Never invent numbers, never output coordinates or places. If unsure, lower confidence.
Message: """


def gemini_extract(text):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=key)
        r = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=PROMPT + text,
            config={"response_mime_type": "application/json", "temperature": 0},
        )
        d = json.loads(r.text)
        d["source"] = "gemini"
        return Extraction(**d)
    except Exception as e:
        print(f"[gemini] call failed, using built-in rules instead: {e}")
        return None


def extract(text: str) -> Extraction:
    return gemini_extract(text) or rules_extract(text)
