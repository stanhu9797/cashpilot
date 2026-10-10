"""Receipt extraction evaluation.

Measures how accurate the AI is on receipts where you already know the right answer.
Re-run this after every prompt or model change to see if accuracy went up or down.

Setup:
  1. Put receipt photos/PDFs in backend/eval/receipts/
  2. Add the correct values for each file to backend/eval/expected.json (see expected.example.json)
  3. From the backend folder run:  python -m eval.run_eval

Results are printed and saved to backend/eval/results/<timestamp>.json so you can compare runs.
"""
import json
import mimetypes
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.client import AIUnavailable, model_name  # noqa: E402
from app.services.receipts import extract_receipt  # noqa: E402

HERE = Path(__file__).parent
TARGET_ACCURACY = 0.90


def norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def check(field, got, want):
    if want is None:
        return None  # not graded
    if field == "total":
        return got is not None and abs(float(got) - float(want)) <= 0.01
    if field == "date":
        return got == want
    if field == "merchant":  # forgiving: "Joe's Coffee" == "JOES COFFEE LLC"
        a, b = norm(got), norm(want)
        return bool(a) and (a in b or b in a)
    return got == want


def main():
    expected_file = HERE / "expected.json"
    if not expected_file.exists():
        print("No eval/expected.json yet. Copy expected.example.json, add your receipts, and fill in the answers.")
        return
    expected = json.loads(expected_file.read_text())
    fields = ["merchant", "date", "total"]
    rows, scores = [], {f: [] for f in fields}
    calibration = {"high_conf_wrong": 0, "low_conf_right": 0}

    for filename, answer in expected.items():
        path = HERE / "receipts" / filename
        if not path.exists():
            print(f"  skip  {filename} (file not found)")
            continue
        ctype = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        started = time.time()
        try:
            data = extract_receipt(path.read_bytes(), ctype).model_dump(mode="json")
        except AIUnavailable as e:
            print(f"  error {filename}: {e}")
            rows.append({"file": filename, "error": str(e)})
            continue
        row = {"file": filename, "seconds": round(time.time() - started, 1), "fields": {}}
        for f in fields:
            ok = check(f, data.get(f), answer.get(f))
            if ok is None:
                continue
            conf = data.get("confidence", {}).get(f, 0)
            scores[f].append(ok)
            if not ok and conf >= 0.8:
                calibration["high_conf_wrong"] += 1
            if ok and conf < 0.8:
                calibration["low_conf_right"] += 1
            row["fields"][f] = {"ok": ok, "got": data.get(f), "want": answer.get(f), "confidence": conf}
        mark = "pass" if all(v["ok"] for v in row["fields"].values()) else "MISS"
        print(f"  {mark}  {filename}")
        for f, v in row["fields"].items():
            if not v["ok"]:
                print(f"         {f}: got {v['got']!r}, expected {v['want']!r} (confidence {v['confidence']})")
        rows.append(row)

    print("\nAccuracy by field")
    summary = {}
    for f in fields:
        if scores[f]:
            acc = sum(scores[f]) / len(scores[f])
            summary[f] = round(acc, 3)
            flag = "" if acc >= TARGET_ACCURACY else f"   below {TARGET_ACCURACY:.0%} target"
            print(f"  {f:<9} {acc:.0%}  ({sum(scores[f])}/{len(scores[f])}){flag}")
    print(
        f"\nConfidence check: {calibration['high_conf_wrong']} wrong answers the AI was confident about "
        f"(these are the dangerous ones), {calibration['low_conf_right']} right answers it flagged anyway."
    )

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"model": model_name(), "summary": summary, "calibration": calibration, "rows": rows}, indent=2))
    print(f"\nSaved {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
