# anki-tools

Local toolkit for managing an Anki collection programmatically via [AnkiConnect](https://ankiweb.net/shared/info/2055492159).

**Requirements:** Anki must be open with the AnkiConnect add-on running on `localhost:8765`.

## Files

### `anki_connect.py`
Thin wrapper over the AnkiConnect HTTP API (v6). Covers: `deck_names`, `model_names`, `model_field_names`, `find_notes`, `notes_info`, `update_note_fields`, `get_tags`, `find_cards`, `cards_info`, `are_suspended`.

### `reconcile.py`
Snapshots the live state of the baseball pitch card decks into `snapshots/`. Re-running overwrites the files; git tracks the diff.

```
python3 reconcile.py
```

## Snapshots

`snapshots/pitch_types.json` and `snapshots/pitching_concepts.json` are the source of truth for the Baseball decks. They are committed to the repo and updated by running `reconcile.py` after editing cards in Anki.

## Decks covered

- `Baseball::Pitch Types` — custom "Pitch Type" note type (Name, Category, Velocity, Spin, HandAtRelease, Movement, Deception, Extra)
- `Baseball::Pitching Concepts` — Basic++, Cloze, Cloze++ note types
