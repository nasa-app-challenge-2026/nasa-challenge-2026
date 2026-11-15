"""Rotation structure and the corrected return-delay rules of the JS yield model.

Perennial years within a block continue one planting. A current stand's age is
unknown: a new planting is checked from the known current year, without inferring
an earlier planting date. Evaluating a monoculture reference remains possible;
the optimizer applies these agronomic constraints only to its proposals.
"""

from __future__ import annotations

import math

from field_shift.algorithm.yield_model.config import CROPS, is_integer


def _number(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return math.nan


def normalize_cycle_offset(offset, cycle_length: int) -> int:
    number = _number(offset)
    if not is_integer(number):
        raise ValueError(f"Paramètre offset invalide ({offset}) : un entier est requis.")
    return int(number) % cycle_length if cycle_length > 0 else 0


def cycle_length(rotation: list[dict]) -> int:
    return sum(entry.get("years") or 1 for entry in rotation)


def to_slots(rotation: list[dict]) -> list[dict]:
    slots = []
    for entry in rotation:
        years = int(entry.get("years") or 1)
        slots.extend(
            {
                "crop": entry.get("crop"),
                "cover": entry.get("cover") if year == years - 1 else None,
            }
            for year in range(years)
        )
    return slots


def entry_start(rotation: list[dict], index: int) -> int:
    start = 0
    for entry in rotation:
        years = int(entry.get("years") or 1)
        if index < start + years:
            return start
        start += years
    return max(0, start - 1)


def planting_starts(rotation: list[dict], crop: str) -> list[int]:
    starts = []
    position = 0
    for entry in rotation:
        years = int(entry.get("years") or 1)
        if entry.get("crop") == crop:
            plantings = 1 if CROPS[crop]["years"] > 1 else years
            starts.extend(position + year for year in range(plantings))
        position += years
    return starts


def lock_reason(rotation: list[dict], index: int, crop: str) -> str | None:
    info = CROPS.get(crop)
    if not info:
        return "Culture inconnue"
    length = len(to_slots(rotation))
    if info["years"] > 1 and index + info["years"] > length:
        return f"Il faut {info['years']} années libres à partir d’ici"
    if 1 < length < info["returnDelay"]:
        return f"Le cycle est plus court que le délai de retour ({info['returnDelay']} ans)"
    replaced_start = entry_start(rotation, index) if info["years"] > 1 else index
    for other in planting_starts(rotation, crop):
        if other == replaced_start:
            continue
        distance = abs(index - other)
        if min(distance, length - distance) < info["returnDelay"]:
            return f"Délai de retour : {info['returnDelay']} ans minimum"
    return None


def rotation_errors(rotation: list[dict]) -> list[str]:
    slots = to_slots(rotation)
    errors = [] if slots else ["La rotation est vide."]
    for index, slot in enumerate(slots):
        crop = slot["crop"]
        if not crop:
            errors.append(f"L’année {index + 1} n’a pas de culture.")
        elif (
            CROPS[crop]["years"] == 1 or entry_start(rotation, index) == index
        ) and lock_reason(rotation, index, crop):
            errors.append(f"{CROPS[crop]['name']} revient trop tôt (année {index + 1}).")
    return errors


def first_year(section: dict, offset=None) -> dict:
    slots = to_slots(section["rotation"])
    if not slots:
        return {"crop": None, "blockStart": True}
    if offset is None:
        offset = section.get("offset", 0)
    position = normalize_cycle_offset(offset, len(slots))
    return {
        "crop": slots[position]["crop"],
        "blockStart": entry_start(section["rotation"], position) == position,
    }


def current_crop_conflict(section: dict, offset=None) -> str | None:
    now = section.get("currentCrop")
    if not isinstance(now, str) or now not in CROPS:
        return None
    if offset is None:
        offset = section.get("offset", 0)
    first = first_year(section, offset)
    crop, block_start = first["crop"], first["blockStart"]
    if not crop or crop not in CROPS:
        return None
    if crop == now and CROPS[crop]["years"] == 1:
        return (
            f"{CROPS[crop]['name']} deux ans de suite : la section est déjà en "
            f"{CROPS[crop]['name'].lower()}"
        )
    if CROPS[crop]["years"] > 1 and not block_start and crop != now:
        return (
            f"La {CROPS[crop]['name'].lower()} ne peut pas commencer en cours de bloc : "
            "elle n’est pas encore semée"
        )
    length = len(to_slots(section["rotation"]))
    start = normalize_cycle_offset(offset, length)
    starts = set(planting_starts(section["rotation"], now))
    # A full traversal also visits the next planting when the opening slot is
    # inside a perennial block and that next planting belongs to cycle two.
    for year in range(1, length + 1):
        position = (start + year - 1) % length
        if position in starts and year < CROPS[now]["returnDelay"]:
            return (
                f"Délai de retour : {CROPS[now]['name']} revient trop tôt "
                f"(année {year}, {CROPS[now]['returnDelay']} ans minimum)."
            )
    return None
