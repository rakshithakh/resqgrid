"""Labelled messages used to measure extraction accuracy (shown on the Evaluation tab)."""

from .core import match_place
from .extract import extract

SET = [
    (
        "Ward 7 mein 40 log chhat par fase hain, paani aur dawai chahiye",
        ["rescue", "medical", "water"],
        40,
        "Ward 7",
    ),
    ("ward 4 25 people stranded, need food and medicine", ["rescue", "medical", "food"], 25, "Ward 4"),
    ("वार्ड 10 में 18 लोग फंसे हैं, पानी और खाना चाहिए", ["rescue", "water", "food"], 18, "Ward 10"),
    ("ವಾರ್ಡ್ 9 ನಲ್ಲಿ 30 ಜನ ಆಹಾರ ಮತ್ತು ನೀರು ಬೇಕು", ["water", "food"], 30, "Ward 9"),
    ("Ward 11: 15 people need drinking water", ["water"], 15, "Ward 11"),
    ("Market Yard 8 workers trapped, one injured, need ambulance", ["rescue", "medical"], 8, "Market Yard"),
    ("Ward 2 insulin required for 2 patients", ["medical"], 2, "Ward 2"),
    ("Ward 8 around 50 people need food packets", ["food"], 50, "Ward 8"),
    (
        "Govt High School camp 120 people need blankets and water",
        ["shelter", "water"],
        120,
        "Govt High School",
    ),
    ("Ward 12 5 people need water", ["water"], 5, "Ward 12"),
    (
        "Civil Hospital 30 patients need medicine and drinking water",
        ["medical", "water"],
        30,
        "Civil Hospital",
    ),
    ("ward 1 12 log khana chahiye", ["food"], 12, "Ward 1"),
    ("Bus Stand 45 people need shelter and food", ["shelter", "food"], 45, "Bus Stand"),
    ("Ward 5 20 people trapped on roof, boat needed", ["rescue"], 20, "Ward 5"),
]


def run():
    n = len(SET)
    ok_t = ok_p = ok_l = 0
    rows = []
    used = {}
    for text, types, people, place in SET:
        e = extract(text)
        loc = match_place(text)
        used[e.source] = used.get(e.source, 0) + 1
        t = set(e.need_types) == set(types)
        p = e.people == people
        exp = match_place(place)
        location_ok = bool(loc and exp and loc[1] == exp[1])
        ok_t += t
        ok_p += p
        ok_l += location_ok
        rows.append(
            {
                "text": text,
                "types_ok": t,
                "people_ok": p,
                "location_ok": location_ok,
                "got_types": e.need_types,
                "got_people": e.people,
            }
        )
    return {
        "n": n,
        "source": ", ".join(f"{k} x{v}" for k, v in used.items()),
        "need_type_accuracy": round(ok_t / n, 3),
        "people_accuracy": round(ok_p / n, 3),
        "location_accuracy": round(ok_l / n, 3),
        "rows": rows,
    }
