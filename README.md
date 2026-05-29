# anki-tools

Local Python toolkit for managing an Anki collection programmatically via AnkiConnect. The primary use case is **leech triage**: surfacing suspended cards that have been repeatedly failed, diagnosing which formulation rule they violate, and reformulating or retiring them.

**Requirements**
- Anki must be open
- AnkiConnect add-on installed and running on `localhost:8765` (add-on code: 2055492159)
- Python 3.9+, no third-party dependencies

---

## The Triage Workflow

This is a three-way process between **the human**, **an LLM**, and **Anki**:

1. The LLM calls `triage.show(N)` via a bash tool to fetch and display the Nth leech note from the live collection.
2. The human and LLM examine the card together. The LLM diagnoses which SuperMemo formulation rule(s) the card may violate and proposes a reformulation.
3. The human decides. They approve, modify, or reject the proposal.
4. If approved, the LLM calls `triage.edit()`, `triage.unsuspend()`, or `triage.retag()` to apply the change directly to the live collection.
5. Repeat from step 1 for the next note.

The script handles all I/O with Anki. The LLM and human handle all judgment. No action modifies Anki unless explicitly approved.

### Starting a session

```
python3 -c "import triage; triage.summary()"
```

This prints a breakdown of all suspended leech notes by deck. Use it to orient at the start of a session.

Then ask the LLM: "Show me leech 0" (or whatever index you want to start from). Notes are sorted worst-first: most lapses descending, lowest ease ascending.

---

## SuperMemo Rules for Leech Diagnosis

When a card is a leech, it usually violates one or more of these rules. The LLM should identify the most likely culprit and propose a fix.

| Rule | Name | Typical symptom |
|------|------|-----------------|
| 4 | Minimum information | Card asks multiple facts at once; hard to pin down what you got wrong |
| 5 | Cloze deletion | Declarative fact stated as Q&A; cloze would be more natural |
| 9 | Avoid sets | Card asks you to recall a list; order is arbitrary |
| 10 | Avoid enumerations | Card asks "how many" or "name all X" |
| 11 | Combat interference | Card is too similar to another card; answers blur together |
| 12 | Optimize wording | Question is ambiguous; multiple valid answers exist |
| 1 | Understand first | Material was never properly understood; card is a symptom |
| 16 | Context cues | No hook to prior knowledge; card floats free of any schema |

A card with 20+ lapses and ease below 150% has almost certainly violated Rule 4 or 11. Look for it.

---

## `triage.py` — Library API

All functions fetch fresh data from AnkiConnect on each call. No local state is maintained between calls.

### Read functions

```python
import triage

triage.summary()
# Prints: total suspended leech notes, count per deck.

triage.show(index)
# Prints: full note display for the note at position `index` in the
# sorted leech list (0-based). Includes all fields (HTML stripped),
# card stats, deck, note type, tags, and note ID.
```

**Reading the `show()` output:**

```
================================================================
  [1/42]  Basic                           ← note type
  deck:  MyDecks::Example Deck           ← deck path
  note:  1000000000001                   ← note ID (use this for edits)
  tags:  Leech
================================================================
  Front:
    What is the capital of Example Country?
  Back:
    Example City

  Cards (1):
  card 1000000000002  [Card 1]  lapses=12  reps=55  ease=149%  interval=1d  [suspended]
```

Card stats:
- `lapses` — times the card was failed after graduating (the leech trigger)
- `reps` — total review count
- `ease` — current ease factor; starts at 250%, each lapse lowers it; below 180% is a red flag
- `interval` — last scheduled interval in days
- `ord` — which card template (0 = first, 1 = second, etc. for note types with multiple cards)
- `[suspended]` / `[buried]` — current scheduler queue state

### Mutation functions

**All mutations print a backup of the prior value before writing. Never call these without the human having seen and approved the change.**

```python
triage.edit(note_id, fields)
# Edit one or more fields. Only the keys present in `fields` are changed.
# Fetches current state first; prints backup before writing.
#
# Example:
triage.edit(1000000000001, {"Front": "new question text"})

triage.unsuspend(note_id)
# Unsuspends all cards belonging to this note.
# Use after reformulating a card — puts it back into the review queue.
#
# Example:
triage.unsuspend(1000000000001)

triage.retag(note_id, remove="", add="")
# Remove and/or add space-separated tags.
# Common pattern after triage: remove "Leech", add "leech-triaged".
#
# Example:
triage.retag(1000000000001, remove="Leech", add="leech-triaged")
```

### Typical action patterns

**Reformulate and return to review:**
```python
triage.edit(NOTE_ID, {"Front": "new question"})
triage.retag(NOTE_ID, remove="Leech", add="leech-triaged")
triage.unsuspend(NOTE_ID)
```

**Retire (leave suspended, mark as done):**
```python
triage.retag(NOTE_ID, remove="Leech", add="leech-retired")
```

**Skip for now:**
```python
# Just call triage.show(next_index) — no mutation needed.
```

---

## `triage.py` — Standalone CLI

```
python3 triage.py
```

Walks through all leech notes interactively. Commands at the `>>>` prompt:

| Command | Action |
|---------|--------|
| `n` / `next` | Next note |
| `p` / `prev` | Previous note |
| `u` / `unsuspend` | Unsuspend this note's cards, advance |
| `edit Field=new value` | Edit a single field (no quotes needed) |
| `retag -OldTag +NewTag` | Remove/add tags |
| `q` / `quit` | Exit |

---

## `anki_connect.py` — Client Reference

Thin wrapper over the AnkiConnect HTTP API (v6). All functions raise `AnkiConnectError` on API errors and `ConnectionError` if Anki is not reachable.

```python
import anki_connect as ac

ac.check_connection()               # → int (API version); raises ConnectionError if down

# Decks / models
ac.deck_names()                     # → list[str]
ac.model_names()                    # → list[str]
ac.model_field_names(model_name)    # → list[str]

# Notes
ac.find_notes(query)                # → list[int]  (note IDs)
ac.notes_info(note_ids)             # → list[dict]  (see shape below)
ac.update_note_fields(note_id, fields)  # fields: {FieldName: value}; partial update
ac.get_tags()                       # → list[str]
ac.add_tags(note_ids, tags)         # tags: space-separated string
ac.remove_tags(note_ids, tags)      # tags: space-separated string

# Cards
ac.find_cards(query)                # → list[int]  (card IDs)
ac.cards_info(card_ids)             # → list[dict]  (see shape below)
ac.are_suspended(card_ids)          # → list[bool]  (parallel to input)
ac.unsuspend_cards(card_ids)        # → None
```

### `notes_info` shape

```python
{
  "noteId":    int,
  "profile":   str,
  "tags":      list[str],
  "fields":    {field_name: {"value": str, "order": int}},
  "modelName": str,
  "mod":       int,   # unix timestamp of last modification
  "cards":     list[int],  # card IDs belonging to this note
}
```

Note: `fields` values are `{"value": ..., "order": ...}` dicts, not plain strings. Use `note["fields"]["Front"]["value"]` to get the text.

### `cards_info` shape (key fields)

```python
{
  "cardId":    int,
  "note":      int,    # parent note ID
  "ord":       int,    # template index (0-based)
  "deckName":  str,
  "modelName": str,
  "fields":    {field_name: {"value": str, "order": int}},
  "factor":    int,    # ease factor × 10 (e.g. 2500 = 250%)
  "interval":  int,    # days
  "reps":      int,
  "lapses":    int,
  "type":      int,    # 0=new 1=learn 2=review 3=relearn
  "queue":     int,    # −2=suspended −1=buried 0=new 1=learn 2=review
  "due":       int,
  "mod":       int,
}
```

### Safety contract

1. **Read before write.** Always fetch current note state with `notes_info()` before calling `update_note_fields()`. Never construct field values from memory or assumptions.
2. **Backup before edit.** `triage.edit()` handles this automatically. If calling `ac.update_note_fields()` directly, print or log the current values first.
3. **No bulk destructive operations.** Mutations in this codebase operate on one note at a time. There is no batch-delete or batch-edit command.

---

## `reconcile.py` — Snapshot Script

Snapshots the live state of specific decks to `snapshots/`. Run after editing cards in Anki to keep the repo in sync. The snapshots are the source of truth for those decks; the rest of the collection is managed through triage.

```
python3 reconcile.py
```

Writes one JSON file per configured deck into `snapshots/`. Edit the `DECKS` dict at the top of `reconcile.py` to point at your own decks.

Each note is stored as:
```json
{
  "noteId": 1000000000001,
  "modelName": "My Note Type",
  "tags": [],
  "mod": 1000000000,
  "fields": {
    "Front": "Question text",
    "Back": "Answer text"
  }
}
```

Field HTML is preserved as-is in snapshots (unlike the triage display, which strips it).

---

