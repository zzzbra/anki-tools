"""
Leech triage tool.

Surfaces problem notes one at a time with their card stats.
Designed for a three-way workflow: this script fetches and applies; the human
and Claude diagnose and decide in conversation.

Sources surfaced:
  - Auto-leeches: suspended cards tagged Leech by Anki
  - Marked cards: any card tagged `marked`, regardless of suspension status

Library API (called from a Claude Code session via bash):
    import triage
    triage.summary()          # how many notes, breakdown by deck and source
    triage.show(0)            # display note at index 0 (sorted worst-first)
    triage.edit(NOTE_ID, {"Front": "new text"})   # field edit with backup
    triage.unsuspend(NOTE_ID)                     # unsuspend all cards
    triage.retag(NOTE_ID, remove="Leech", add="leech-triaged")
    triage.show_templates("My Note Type")  # which fields appear on which card

Standalone CLI:
    python3 triage.py
"""

import html
import re
import sys

import anki_connect as ac

LEECH_QUERY  = "is:suspended tag:Leech"
MARKED_QUERY = "tag:marked"

# Set to a string prefix to highlight matching tags as a dedicated line in
# show() output. Set to None to disable. Example: "todo:"
TODO_PREFIX: str | None = None


# ---------------------------------------------------------------------------
# HTML → plain text
# ---------------------------------------------------------------------------

def _plain(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<img[^>]*alt=['\"]([^'\"]+)['\"][^>]*>", r"[image: \1]", text)
    text = re.sub(r"<img[^>]*src=['\"]([^'\"]+)['\"][^>]*>", r"[image: \1]", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load() -> list[tuple[dict, list[dict]]]:
    """
    Return list of (note, cards) for all notes needing triage, sorted
    worst-first (lapses desc, ease asc). Each card dict has a `_sources`
    key: a list containing "leech", "marked", or both.
    """
    leech_ids  = set(ac.find_cards(LEECH_QUERY))
    marked_ids = set(ac.find_cards(MARKED_QUERY))
    all_ids    = leech_ids | marked_ids

    if not all_ids:
        return []

    cards = ac.cards_info(list(all_ids))

    for card in cards:
        sources = []
        if card["cardId"] in leech_ids:
            sources.append("leech")
        if card["cardId"] in marked_ids:
            sources.append("marked")
        card["_sources"] = sources

    note_to_cards: dict[int, list[dict]] = {}
    for card in cards:
        note_to_cards.setdefault(card["note"], []).append(card)

    notes = ac.notes_info(list(note_to_cards.keys()))
    note_map = {n["noteId"]: n for n in notes}

    pairs = [
        (note_map[note_id], note_cards)
        for note_id, note_cards in note_to_cards.items()
    ]

    def sort_key(pair):
        _, note_cards = pair
        max_lapses = max(c["lapses"] for c in note_cards)
        min_ease   = min(c["factor"] for c in note_cards)
        return (-max_lapses, min_ease)

    pairs.sort(key=sort_key)
    return pairs


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _get_template_names(model_name: str) -> dict[int, str]:
    """Return {ord: template_name} for a note type."""
    try:
        templates = ac.model_templates(model_name)
        return {i: name for i, name in enumerate(templates.keys())}
    except ac.AnkiConnectError:
        return {}


def _fmt_card(card: dict, template_name: str | None = None) -> str:
    queue_label = {-2: "suspended", -1: "buried", 0: "new",
                   1: "learning", 2: "review", 3: "relearning"}.get(card["queue"], str(card["queue"]))
    ease    = card["factor"] / 10
    tmpl    = f"  [{template_name}]" if template_name else f"  ord={card['ord']}"
    sources = card.get("_sources", [])
    src_str = f"  ({', '.join(sources)})" if sources else ""
    return (
        f"  card {card['cardId']}{tmpl}{src_str}  "
        f"lapses={card['lapses']}  reps={card['reps']}  "
        f"ease={ease:.0f}%  interval={card['interval']}d  [{queue_label}]"
    )


def show(index: int) -> None:
    """Display the note at position `index` in the sorted triage list."""
    pairs = _load()
    if not pairs:
        print("No notes to triage.")
        return
    if index < 0 or index >= len(pairs):
        print(f"Index {index} out of range (0–{len(pairs)-1}).")
        return

    note, cards = pairs[index]
    total = len(pairs)
    deck  = cards[0]["deckName"]

    print(f"\n{'='*64}")
    print(f"  [{index+1}/{total}]  {note['modelName']}")
    print(f"  deck:  {deck}")
    print(f"  note:  {note['noteId']}")
    print(f"  tags:  {', '.join(note['tags']) or '(none)'}")
    if TODO_PREFIX:
        prefixed = [t for t in note["tags"] if t.startswith(TODO_PREFIX)]
        if prefixed:
            print(f"  {TODO_PREFIX.rstrip(':')}:  {', '.join(prefixed)}")
    print(f"{'='*64}")

    for field_name, data in note["fields"].items():
        value = _plain(data["value"])
        if value:
            lines = value.split("\n")
            print(f"  {field_name}:")
            for line in lines:
                if line.strip():
                    print(f"    {line}")

    template_names = _get_template_names(note["modelName"])
    print(f"\n  Cards ({len(cards)}):")
    for card in sorted(cards, key=lambda c: c["ord"]):
        print(_fmt_card(card, template_names.get(card["ord"])))
    print()


def summary() -> None:
    """Print a count of triage notes broken down by deck and source."""
    pairs = _load()
    if not pairs:
        print("No notes to triage.")
        return

    from collections import Counter
    deck_counts: Counter = Counter()
    source_counts: Counter = Counter()

    for note, cards in pairs:
        deck_counts[cards[0]["deckName"]] += 1
        all_sources = {s for c in cards for s in c.get("_sources", [])}
        for s in all_sources:
            source_counts[s] += 1

    total = len(pairs)
    print(f"\nNotes to triage: {total}\n")
    print(f"  By source:")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {count:>4}  {src}")
    print(f"\n  By deck:")
    for deck, count in sorted(deck_counts.items(), key=lambda x: -x[1]):
        print(f"    {count:>4}  {deck}")
    print()


# ---------------------------------------------------------------------------
# Template inspection
# ---------------------------------------------------------------------------

def _extract_fields(template_html: str) -> list[str]:
    """Return field names referenced in a template, in order of appearance."""
    seen = []
    for raw in re.findall(r"\{\{([^}]+)\}\}", template_html):
        name = re.sub(r"^(edit:|type:|hint:|[#/^])", "", raw).strip()
        if name and name not in ("FrontSide",) and name not in seen:
            seen.append(name)
    return seen


def show_templates(model_name: str) -> None:
    """Print a clean summary of each template's front and back fields."""
    templates = ac.model_templates(model_name)
    print(f"\n{model_name}")
    print("=" * len(model_name))
    for name, tmpl in templates.items():
        front_fields = _extract_fields(tmpl["Front"])
        back_fields  = _extract_fields(tmpl["Back"])
        print(f"\n  {name}")
        print(f"    front: {', '.join(front_fields) or '—'}")
        print(f"    back:  {', '.join(back_fields) or '—'}")
    print()


# ---------------------------------------------------------------------------
# Mutations  (all fetch-current-state first; caller gets backup printed)
# ---------------------------------------------------------------------------

def edit(note_id: int, fields: dict[str, str]) -> None:
    """
    Edit fields on a note. Prints the backed-up prior values before writing.
    Only the keys present in `fields` are changed.
    """
    current = ac.notes_info([note_id])[0]
    backup  = {name: data["value"] for name, data in current["fields"].items()}

    print("Backup of current field values:")
    for name, value in backup.items():
        if name in fields:
            print(f"  {name}: {_plain(value)!r}")

    ac.update_note_fields(note_id, fields)
    print("Updated:")
    for name, value in fields.items():
        print(f"  {name}: {value!r}")


def unsuspend(note_id: int) -> None:
    """Unsuspend all cards belonging to this note."""
    current  = ac.notes_info([note_id])[0]
    card_ids = current["cards"]
    ac.unsuspend_cards(card_ids)
    print(f"Unsuspended {len(card_ids)} card(s) for note {note_id}.")


def retag(note_id: int, *, remove: str = "", add: str = "") -> None:
    """Remove and/or add tags on a note. Pass space-separated tag strings."""
    if remove:
        ac.remove_tags([note_id], remove)
        print(f"Removed tags: {remove}")
    if add:
        ac.add_tags([note_id], add)
        print(f"Added tags: {add}")


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    pairs = _load()
    if not pairs:
        print("No notes to triage.")
        return

    total = len(pairs)
    index = 0
    print(f"\n{total} notes to triage. Commands: n(ext), p(rev), u(nsuspend), q(uit)")
    print("  edit <field>=<value>   — edit a single field")
    print("  retag -<tag> +<tag>    — remove/add tags (prefix with - or +)")

    while 0 <= index < total:
        show(index)
        try:
            raw = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        note_id  = pairs[index][0]["noteId"]

        if raw in ("n", "next"):
            index += 1
        elif raw in ("p", "prev"):
            index = max(0, index - 1)
        elif raw in ("u", "unsuspend"):
            unsuspend(note_id)
            index += 1
        elif raw in ("q", "quit"):
            break
        elif raw.startswith("edit "):
            rest = raw[5:].strip()
            if "=" not in rest:
                print("Usage: edit <FieldName>=<new value>")
                continue
            field, _, value = rest.partition("=")
            edit(note_id, {field.strip(): value.strip()})
        elif raw.startswith("retag "):
            parts = raw[6:].split()
            to_remove = " ".join(p[1:] for p in parts if p.startswith("-"))
            to_add    = " ".join(p[1:] for p in parts if p.startswith("+"))
            retag(note_id, remove=to_remove, add=to_add)
        else:
            print("Unknown command.")

    print("Done.")


if __name__ == "__main__":
    try:
        ac.check_connection()
    except ConnectionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    _cli()
