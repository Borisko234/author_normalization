import re
import pandas as pd
import json
from functools import lru_cache

from symspellpy import Verbosity
from index_original_dictionary import get_sym_spell
from thefuzz import fuzz
from collections import defaultdict


_df = None
results = {}


def get_df():
    global _df
    if _df is None:
        filepath = "ps_supplier/ps_supplier.csv"

        column_names = ['id', 'name', 'normalized_name', 'created_at', 'updated_at',
                        'active', 'code', 'first_name', 'last_name', 'birth_year',
                        'death_year', 'description', 'col13', 'col14', 'col15',
                        'col16', 'col17']
        _df = pd.read_csv(
            filepath,
            sep=";",
            names=column_names,
            usecols=['name'],
            dtype={'name': str},
            low_memory=False
        )
    return _df

_name_index: dict[str, set[str]] = defaultdict(set)

def build_name_index():
    global _name_index
    df = get_df()
    for full_name in df['name'].dropna():
        for token in re.split(r'[\s,.\-]+', full_name.lower()):
            token = token.strip()
            if token:
                _name_index[token].add(full_name.lower())

def split_name(name):
    name = re.sub(r'\([^)]*\)?', '', name)
    parts = re.split(r'[\s.,-]+', name.lower().strip())
    return [p for p in parts if p]

def split_people(name: str) -> list[str]:
    return [n.strip() for n in re.split(r'[,]', name) if n.strip()]

def get_first_and_last_name(name: list):
    if len(name) < 2:
        return name
    return [name[0], name[-1]]

@lru_cache(maxsize=10000)
def normalize_string(string):
    if len(string) == 2 and string.isupper():
        return string[0].strip().lower() + " " + string[1].strip().lower()
    return string.strip().lower()

def correct_text(raw_input: str, ss) -> str:
    results = ss.lookup(raw_input, Verbosity.CLOSEST, max_edit_distance=2)
    if len(results) <= 0:
        return "Not in database, do you want to use an AI for this?"
    return results[0].term if results else raw_input

@lru_cache(maxsize=50_000)
def get_best_term(name: str, ss = None, other_name_parts: tuple = ()) -> tuple[str, int]:
    if ss is None:
        ss = get_sym_spell()
    original_results = ss.lookup(name, Verbosity.CLOSEST, max_edit_distance=0)

    if not original_results:
        return name, 0
    best = original_results[0]
    if best.count <= 1:
        typo_results = ss.lookup(name, Verbosity.ALL, max_edit_distance=1)

        better = sorted(
        [r for r in typo_results if r.term != name and r.count > 1 and len(r.term) >= len(name) - 0],
        key=lambda x: x.count,
        reverse=True)

        for candidate in better:
            if _is_compatible_with_other_parts(candidate.term, other_name_parts):
                best = candidate
                break

    return best.term, best.count

def _is_compatible_with_other_parts(surname: str, other_parts: tuple) -> bool:
    if not other_parts:
        return True
    matches = _name_index.get(surname.lower(), set())
    if not matches:
        return False
    # check if any matched row also contains one of the other name parts
    for part in other_parts:
        if part and len(part) > 1:
            part_matches = _name_index.get(part.lower(), set())
            if matches & part_matches:
                return True
    return False

def get_surname(names: tuple, ss) -> str | None:
    min_count = float('inf')
    surname = None

    for name in names:
        if len(name) <= 1:
            continue
        name = normalize_string(name)
        other_parts = tuple(n for n in names if n != name)
        term, count = get_best_term(name, ss, other_parts)
        if term is None:
            continue
        if count < min_count:
            min_count = count
            surname = term

    return surname


@lru_cache(maxsize=10000)
def normalize_order(name: str) -> tuple[str]:
    """Remove punctuation, split, sort alphabetically so order doesn't matter."""
    parts = re.split(r'[\s,.]+', name.strip().lower())
    return tuple(sorted(p.strip() for p in parts if p.strip()))


def to_initials_sorted(name: str) -> list[str]:
    parts = normalize_order(name)
    return sorted(part[0] for part in parts)


def is_consistent(name1: str, name2: str) -> bool:
    parts1 = normalize_order(name1)
    parts2 = normalize_order(name2)

    if len(parts1) != len(parts2):
        return False

    for p1, p2 in zip(parts1, parts2):
        if len(p1) > 1 and len(p2) > 1:
            # Use fuzzy matching for full names to handle typos
            if p1 != p2 and fuzz.ratio(p1, p2) < 80:
                return False
        elif len(p1) == 1 and len(p2) > 1:
            if not p2.startswith(p1):
                return False
        elif len(p2) == 1 and len(p1) > 1:
            if not p1.startswith(p2):
                return False
    return True

def same_person(name1: str, name2: str) -> bool:
    return to_initials_sorted(name1) == to_initials_sorted(name2) and is_consistent(name1, name2)

def create_key(full_name: list, surname: str, ss=None) -> str:
    """Replaces create_final_name — no fuzz, just direct comparison"""
    # initials = []
    # for name in full_name:
    #     name = normalize_string(name)
    #     term, _ = get_best_term(name, ss)
    #     resolved = term if term else name
    #     if fuzz.ratio(resolved, surname) < 80:
    #
    #     # if resolved != surname:
    #         initials.append(resolved[0])
    # return f"{surname} {' '.join(initials)}"
    initials = [
        get_best_term(normalize_string(n), ss)[0][0]  # just the initial
        for n in full_name
        if fuzz.ratio(get_best_term(normalize_string(n), ss)[0], surname) < 80
    ]
    return f"{surname} {' '.join(initials)}"

def create_full_key(full_name: list, surname: str, ss=None) -> str:
    """Replaces create_full_final_name"""
    first_names = []
    for name in full_name:
        name = normalize_string(name)
        term, _ = get_best_term(name, ss)
        resolved = term if term else name
        # if resolved != surname:
        if fuzz.ratio(resolved, surname) < 80:
            first_names.append(resolved)
    return f"{surname} {' '.join(first_names)}"

def create_final_name(full_name: list, surname: str):
    first_name = []
    surname = normalize_string(surname)
    for name in full_name:
        name = normalize_string(name)
        if fuzz.ratio(name, surname) <= 75:
            first_name.append(name[0])
    return f"{surname} {' '.join(first_name)}"


def create_full_final_name(full_name: list, surname: str):
    first_names = []
    surname = normalize_string(surname)
    for name in full_name:
        name = normalize_string(name)
        if fuzz.ratio(name, surname) <= 75:
            first_names.append(name)
    return f"{surname} {' '.join(first_names)}"

def pipeline(name: str, ss):
    splited_name = split_name(name)
    first_last = get_first_and_last_name(splited_name)
    surname = get_surname(first_last, ss)

    if surname is None:
        return
    key = create_key(splited_name, surname, ss)

    if key not in results:
        results[key] = {"original_name": [name], "books": []}
        return

    if name in results[key]["original_name"]:
        return

    if all(same_person(name, existing) for existing in results[key]["original_name"]):
        results[key]["original_name"].append(name)
    else:
        full_key = create_full_key(splited_name, surname, ss)
        if full_key == key:
            full_key = f"{key} ({name.lower()})"
        if full_key not in results:
            results[full_key] = {"original_name": [name], "books": []}
        elif name not in results[full_key]["original_name"]:
            results[full_key]["original_name"].append(name)


if __name__ == "__main__":
    from itertools import islice
    import time
    ss = get_sym_spell()
    start = time.time()

    i = 0
    # names = ["J. K. Rowling", "Joanne K. Rowling", "Joanne Kathleen Rowling", "Rowling, Joanne K.", "Mary GrandPré; J. K. Rowling", "J. K. Rowling Robert", "Homer"]
    get_df()
    build_name_index()
    names = _df['name'].fillna('')
    for raw in names:
        i +=1
        print(i)
        people = split_people(raw)
        for person in people:
            pipeline(person, ss)

    with open("output3.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # first = "Brachma¿ski"
    # typo_results = ss.lookup(first, Verbosity.ALL, max_edit_distance=2)
    # for r in typo_results:
    #     print(f"{r.count} {r.term} {r.distance}")

    # print(f"first {get_best_term(first, ss)[0]} {get_best_term(first, ss)[1]}")
    # print(f"last {get_best_term(last, ss)[0]} {get_best_term(last, ss)[1]}")

    print(f"Execution time: {time.time() - start:.2f} seconds")