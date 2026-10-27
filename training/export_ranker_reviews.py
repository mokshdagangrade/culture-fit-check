"""Export saved generation history to JSONL for signal-level human review.

Usage: python training/export_ranker_reviews.py history.json --output training/out/ranker_reviews.jsonl

Input is a /history response ({"entries": [...]}) or a JSON array of history
entries. This command is offline: it never calls an LLM or connects to MongoDB.
Scores are machine judgments, not human labels. Older histories have unknown
scores for omitted candidates; these remain unassessed, never negative labels.
"""
import argparse
import json
from pathlib import Path


def review_rows(entries):
    for entry in entries:
        for result_index, result in enumerate(entry.get("results") or []):
            selection = (result.get("grounding_context") or {}).get("signal_selection") or {}
            audit = selection.get("ranking_audit") or {}
            selected = selection.get("selected", [])
            selected_ids = {row.get("signal_id") for row in selected if row.get("signal_id")}
            assessments = audit.get("assessments")
            if assessments is None:
                # Legacy history only stored selected scores. Match by stable ID.
                known = {row["signal_id"]: row for row in selected if row.get("signal_id")}
                assessments = []
                for index, signal in enumerate(selection.get("pool", [])):
                    judgment = known.get(signal.get("signal_id"), {})
                    assessments.append({**signal, "candidate_index": index,
                                        "score": judgment.get("score"),
                                        "why": judgment.get("why", ""),
                                        "assessment_status": "assessed" if judgment.get("score") is not None else "unassessed"})
            for signal in assessments:
                yield {
                    "history_id": str(entry.get("id", entry.get("_id", ""))),
                    "project_id": entry.get("project_id"),
                    "created_at": entry.get("created_at"),
                    "result_index": result_index,
                    "brief": audit.get("brief", entry.get("prompt", "")),
                    "company": audit.get("company"),
                    "state": audit.get("state", result.get("state")),
                    "as_of": selection.get("as_of"),
                    "method": selection.get("method"),
                    "signal": {key: value for key, value in signal.items()
                               if key not in ("score", "why", "assessment_status")},
                    "model_score": signal.get("score"),
                    "model_reason": signal.get("why", ""),
                    "assessment_status": signal.get("assessment_status", "unassessed"),
                    "selected_for_generation": signal.get("signal_id") in selected_ids,
                    "human_relevance": None,
                    "human_suitability": None,
                    "human_notes": "",
                    "reviewer": "",
                }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history", type=Path, help="Saved /history JSON response or array")
    parser.add_argument("--output", type=Path, required=True, help="New JSONL review file")
    args = parser.parse_args()
    data = json.loads(args.history.read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list) or any(not isinstance(row, dict) for row in entries):
        parser.error("Input must be an array of history entries or an object containing entries")
    # Validate/serialize the saved history before creating any output. A malformed
    # later entry must not leave a partial review file that looks complete.
    try:
        lines = [json.dumps(row, ensure_ascii=False) + "\n" for row in review_rows(entries)]
    except (AttributeError, TypeError, ValueError) as exc:
        parser.error(f"Invalid history structure: {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite an existing file that may already contain human reviews.
    with args.output.open("x", encoding="utf-8") as output:
        output.writelines(lines)
    print(f"Exported {len(lines)} candidate pairs to {args.output}")


if __name__ == "__main__":
    main()
