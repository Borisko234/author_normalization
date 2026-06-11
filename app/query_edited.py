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
    if ',' not in name:
        return [name.strip()]

    parts = [n.strip() for n in name.split(',')]

    # If it's "Doe, Jane, Smith, Bob", parts are ['Doe', 'Jane', 'Smith', 'Bob']
    # If all parts are single words, and there are >= 4 parts, it's likely multiple authors in "Last, First" format
    if all(len(p.split()) == 1 for p in parts) and len(parts) >= 4 and len(parts) % 2 == 0:
        new_people = []
        for i in range(0, len(parts), 2):
            new_people.append(f"{parts[i]}, {parts[i+1]}")
        return new_people

    # If all parts are single words and there are 2 or 3, it's likely ONE author "Last, First" or "Last, First Middle"
    if all(len(p.split()) == 1 for p in parts) and len(parts) <= 3:
        return [name.strip()]

    # If some parts have multiple words, commas might be person delimiters
    new_people = []
    i = 0
    while i < len(parts):
        current_part = parts[i]
        if len(current_part.split()) >= 2:
            new_people.append(current_part)
            i += 1
        else:
            if i + 1 < len(parts) and len(parts[i+1].split()) == 1:
                new_people.append(f"{current_part}, {parts[i+1]}")
                i += 2
            else:
                new_people.append(current_part)
                i += 1
    return new_people

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
    people = split_people(name)
    
    person_keys = []
    for person in people:
        splited_name = split_name(person)
        if not splited_name:
            continue
        
        first_last = get_first_and_last_name(splited_name)
        surname = get_surname(tuple(first_last), ss)
        
        if surname is None:
            # Fallback for single word names or if surname detection fails
            surname = splited_name[-1]
            
        key = create_key(splited_name, surname, ss)
        person_keys.append((key, splited_name, surname))

    if not person_keys:
        return
        
    # Create the combined key
    combined_key = ", ".join(pk[0] for pk in person_keys)

    if combined_key not in results:
        results[combined_key] = {"original_name": [name], "books": []}
        return

    if name in results[combined_key]["original_name"]:
        return

    # Consistency check - if it's a single author, we can use the original logic
    if len(people) == 1:
        key, splited_name, surname = person_keys[0]
        if all(same_person(name, existing) for existing in results[combined_key]["original_name"]):
            results[combined_key]["original_name"].append(name)
        else:
            full_key = create_full_key(splited_name, surname, ss)
            if full_key == combined_key:
                full_key = f"{combined_key} ({name.lower()})"
            if full_key not in results:
                results[full_key] = {"original_name": [name], "books": []}
            elif name not in results[full_key]["original_name"]:
                results[full_key]["original_name"].append(name)
    else:
        # For multiple authors, just append if it maps to the same combined key for now
        # as the original consistency check was designed for single authors
        if name not in results[combined_key]["original_name"]:
            results[combined_key]["original_name"].append(name)


if __name__ == "__main__":
    import time
    ss = get_sym_spell()
    start = time.time()
    names = ["Mareš, Antonín","Mareš, Antonín", "Castro Francisca, Rodero Ignacio, Sardinero Carmen, Rebollo Begona", "Andreas Brandhorst", "Brandhorst, Andreas", "Pike Aprilynne", "Pike Aprliynne", "Aleš Kisela", "Alessandrini, Adriano (Professor of Transportation Science and Economics, Department of Civil and Environmental Engineer", "" ]
    # print(split_people(names))
    # print(len(split_people(names)))
    i = 0
    # get_df()
    # build_name_index()
    # names = _df['name'].fillna('')
    for raw in names:
        # print(raw)
        i +=1
        print(i)
        # people = split_people(raw)
        # if len(people) >= 2:

            # for person in people:
            # print(people)
            # print(raw)
        # else:
        print(split_name(raw))
        for person in split_people(raw):
            print(f"printing perso : {person}")
            splited_name = split_name(person)
            print(splited_name)
            if not splited_name:
                continue

            first_last = get_first_and_last_name(splited_name)
            print(first_last)
            surname = get_surname(tuple(first_last), ss)
            print(surname)
        # pipeline(raw, ss)
        # for person in people:
        #     pipeline(person, ss)
    #
    with open("output3.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Execution time: {time.time() - start:.2f} seconds")