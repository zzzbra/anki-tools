"""
Snapshot the live state of baseball pitch notes into the repo.

Writes:
  snapshots/pitch_types.json        — all notes in Baseball::Pitch Types
  snapshots/pitching_concepts.json  — all notes in Baseball::Pitching Concepts

Run this any time you want to sync the repo with your live collection.
Re-running overwrites the files; git tracks the diff.
"""

import json
import os
import sys

import anki_connect as ac

SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")

DECKS = {
    "pitch_types": 'deck:"Baseball::Pitch Types"',
    "pitching_concepts": 'deck:"Baseball::Pitching Concepts"',
}


def fetch_notes(query: str) -> list[dict]:
    note_ids = ac.find_notes(query)
    if not note_ids:
        return []
    raw = ac.notes_info(note_ids)
    notes = []
    for n in raw:
        notes.append({
            "noteId": n["noteId"],
            "modelName": n["modelName"],
            "tags": sorted(n["tags"]),
            "mod": n["mod"],
            "fields": {
                name: data["value"]
                for name, data in n["fields"].items()
            },
        })
    return sorted(notes, key=lambda n: n["noteId"])


def write_snapshot(name: str, notes: list[dict]) -> str:
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    path = os.path.join(SNAPSHOTS_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def summarize(name: str, notes: list[dict]) -> None:
    from collections import Counter
    model_counts = Counter(n["modelName"] for n in notes)
    print(f"\n{name} ({len(notes)} notes)")
    for model, count in sorted(model_counts.items()):
        fields = ac.model_field_names(model)
        print(f"  {model} × {count}  |  fields: {', '.join(fields)}")


def main() -> None:
    try:
        version = ac.check_connection()
        print(f"AnkiConnect v{version} reachable.")
    except ConnectionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    for name, query in DECKS.items():
        notes = fetch_notes(query)
        path = write_snapshot(name, notes)
        summarize(name, notes)
        print(f"  → wrote {len(notes)} notes to {path}")


if __name__ == "__main__":
    main()
