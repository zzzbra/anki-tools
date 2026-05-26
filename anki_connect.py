"""
Thin wrapper over the AnkiConnect HTTP API (version 6).

All methods raise AnkiConnectError if AnkiConnect returns a non-null error,
and ConnectionError if the server is unreachable.
"""

import json
import urllib.error
import urllib.request
from typing import Any

ANKI_CONNECT_URL = "http://localhost:8765"
API_VERSION = 6


class AnkiConnectError(Exception):
    pass


def _invoke(action: str, **params) -> Any:
    payload = {"action": action, "version": API_VERSION}
    if params:
        payload["params"] = params

    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        ANKI_CONNECT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read())
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Cannot reach AnkiConnect at {ANKI_CONNECT_URL}. "
            "Is Anki open with the AnkiConnect add-on running?"
        ) from exc

    if result.get("error") is not None:
        raise AnkiConnectError(result["error"])

    return result["result"]


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------

def check_connection() -> int:
    """Return the AnkiConnect API version. Raises ConnectionError if unreachable."""
    return _invoke("version")


# ---------------------------------------------------------------------------
# Decks and models
# ---------------------------------------------------------------------------

def deck_names() -> list[str]:
    """Return all deck names (includes parent and child decks)."""
    return _invoke("deckNames")


def model_names() -> list[str]:
    """Return all note-type (model) names."""
    return _invoke("modelNames")


def model_field_names(model_name: str) -> list[str]:
    """Return ordered field names for a note type."""
    return _invoke("modelFieldNames", modelName=model_name)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def find_notes(query: str) -> list[int]:
    """Return note IDs matching an Anki search query."""
    return _invoke("findNotes", query=query)


def notes_info(note_ids: list[int]) -> list[dict]:
    """
    Return full note objects for the given IDs.

    Each note dict has:
      noteId    int
      profile   str
      tags      list[str]
      fields    dict[str, {"value": str, "order": int}]
      modelName str
      mod       int  (unix timestamp of last modification)
      cards     list[int]
    """
    return _invoke("notesInfo", notes=note_ids)


def update_note_fields(note_id: int, fields: dict[str, str]) -> None:
    """
    Overwrite specific fields on a note. Only the keys present in `fields`
    are changed; all other fields are left untouched by AnkiConnect.

    Caller is responsible for fetching and backing up current field values
    before calling this.
    """
    _invoke("updateNoteFields", note={"id": note_id, "fields": fields})


def get_tags() -> list[str]:
    """Return all tags in the collection."""
    return _invoke("getTags")


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

def find_cards(query: str) -> list[int]:
    """Return card IDs matching an Anki search query."""
    return _invoke("findCards", query=query)


def cards_info(card_ids: list[int]) -> list[dict]:
    """
    Return card objects for the given IDs.

    Each card dict has (among others):
      cardId      int
      note        int      (parent note ID)
      ord         int      (template index within the note type)
      deckName    str
      modelName   str
      fields      dict[str, {"value": str, "order": int}]
      fieldOrder  int      (which field is the question field for this card)
      factor      int      (ease factor, e.g. 2500 = 250%)
      interval    int      (days)
      reps        int
      lapses      int
      type        int      (0=new, 1=learn, 2=review, 3=relearn)
      queue       int      (−2=suspended, −1=buried, 0=new, 1=learn, 2=review)
      due         int
      mod         int      (unix timestamp)
    """
    return _invoke("cardsInfo", cards=card_ids)


def are_suspended(card_ids: list[int]) -> list[bool]:
    """
    Return a parallel list of booleans indicating whether each card is suspended.
    Order matches the input list.
    """
    return _invoke("areSuspended", cards=card_ids)


def unsuspend_cards(card_ids: list[int]) -> None:
    """Unsuspend the given cards."""
    _invoke("unsuspend", cards=card_ids)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def add_tags(note_ids: list[int], tags: str) -> None:
    """Add space-separated tags to the given notes."""
    _invoke("addTags", notes=note_ids, tags=tags)


def remove_tags(note_ids: list[int], tags: str) -> None:
    """Remove space-separated tags from the given notes."""
    _invoke("removeTags", notes=note_ids, tags=tags)
