import re
import sys

import pandas as pd
import json
from functools import lru_cache

from symspellpy import Verbosity
from index_original_dictionary import get_sym_spell
from thefuzz import fuzz
from collections import defaultdict
from math import floor


_df = None
results = {}

total_distinct_names = 0
merged_names_count = 0

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
            usecols=['id', 'name', 'description', 'col13'],
            dtype={'id': str, 'name': str, 'description': str, 'col13':str},
            low_memory=False,
        )
    return _df

_name_index: dict[str, set[str]] = defaultdict(set)


def strip_nested_parentheses(text: str) -> str:
    """Removes parenthetical content, handling deeply nested parentheses perfectly."""
    result = []
    paren_depth = 0
    for char in text:
        if char == '(':
            paren_depth += 1
        elif char == ')':
            if paren_depth > 0:
                paren_depth -= 1
        elif paren_depth == 0:
            result.append(char)
    return "".join(result)


def build_name_index():
    global _name_index
    df = get_df()
    for full_name in df['name'].dropna():
        for token in re.split(r'[\s,.\-]+', full_name.lower()):
            token = token.strip()
            if token:
                _name_index[token].add(full_name.lower())

def split_name(name):
    name = str(name)
    name = strip_nested_parentheses(name)
    name = re.sub(r'\([^)]*\)?', '', name)

    # Fix missing &# in numeric entities before unescaping
    name = re.sub(r'(\d{4,5});', r'&#\1;', name)
    import html
    name = html.unescape(name)
    name = re.sub(r'[\\"\’\'#]', ' ', name)

    parts = re.split(r'[\s.,\-:;+&/]+', name.lower().strip())

    return [p for p in parts if p.strip() and not p.startswith('&')]

def split_people(name: str) -> list[str]:
    # Fix missing &# in numeric entities before unescaping
    name = re.sub(r'(\d{4,5});', r'&#\1;', name)
    import html
    name = html.unescape(name)
    names = [n.strip() for n in re.split(r'[;]', name) if n.strip()]
    if len(names) == 1:
        splitted_names = [n.strip() for n in re.split(r'[,]', name) if n.strip()]
        for name in splitted_names:
            if len([n.strip() for n in re.split(r'[ ]', name) if n.strip()]) <= 1:
                return names
        return splitted_names
    return names

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
    if not any(c.isalpha() for c in name):
        return name, float("inf")
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

# def get_surname(names: tuple, ss) -> str | None:
#     min_count = float('inf')
#     surname = None
#
#     for name in names:
#         if len(name) <= 1:
#             continue
#         if name.isnumeric():
#             continue
#         name = normalize_string(name)
#         other_parts = tuple(n for n in names if n != name)
#         term, count = get_best_term(name, ss, other_parts)
#         if term is None:
#             continue
#         if count < min_count:
#             min_count = count
#             surname = term
#
#     if surname is None and names != []:
#         return names[0]
#     else:
#         return surname

def get_surname(names: list, ss) -> str:
    if not names:
        return "unknown"
    if len(names) == 1:
        return names[0]

    first_last_names = [names[0], names[-1]]
    clean_names = names


    worst_count = float('inf')

    surname = None

    for name in first_last_names:

        if len(name) <= 1:
            if len(names) == 3:
                if len(names[1]) > 1:
                    name = names[1]
        if name.isnumeric():
            continue

        name_clean = normalize_string(name)

        other_parts = tuple(n for n in clean_names if n != name)

        term, count = get_best_term(name_clean, ss, other_parts)

        if term is None or term.strip() in ['', '-']:
            term = name_clean
            count = 1

        if count < worst_count:
            worst_count = count
            surname = term

    return surname if (surname and surname.strip() not in ['', '-']) else names[0]



@lru_cache(maxsize=10000)
def normalize_order(name: str) -> tuple[str]:
    """Remove punctuation, split, sort alphabetically so order doesn't matter."""
    # Fix missing &# in numeric entities
    name = re.sub(r'(\d{4,5});', r'&#\1;', name)
    import html
    name = html.unescape(name)
    name = re.sub(r'&#?\d+;?', ' ', name)  

    name = re.sub(r'[\\"\’\'#]', ' ', name)

    parts = re.split(r'[\s.,\-:;+&/]+', name.lower().strip())
    return tuple(sorted(p.strip() for p in parts if p.strip()))


def to_initials_sorted(name: str) -> list[str]:
    parts = normalize_order(name)
    return sorted(part[0] for part in parts)


def is_consistent(name1: str, name2: str) -> bool:
    parts1 = normalize_order(name1)
    parts2 = normalize_order(name2)

    # Allow merging if they are both undecodable numeric fragments
    if not any(not p.isdigit() for p in parts1) and not any(not p.isdigit() for p in parts2):
        return True

    if len(parts1) != len(parts2):
        return False

    for p1, p2 in zip(parts1, parts2):
        if len(p1) > 1 and len(p2) > 1:
            # Use fuzzy matching for full names to handle typos
            if p1 != p2 and fuzz.ratio(p1, p2) < 70:
                return False
        elif len(p1) == 1 and len(p2) > 1:
            if not p2.startswith(p1):
                return False
        elif len(p2) == 1 and len(p1) > 1:
            if not p1.startswith(p2):
                return False
    return True

def same_person(name1: str, name2: str) -> bool:
    parts1 = normalize_order(name1)
    parts2 = normalize_order(name2)
    # Allow merging if they are both undecodable numeric fragments
    if not any(not p.isdigit() for p in parts1) and not any(not p.isdigit() for p in parts2):
        return True
    return to_initials_sorted(name1) == to_initials_sorted(name2) and is_consistent(name1, name2)

def create_key(full_name: list, surname: str, ss=None) -> str:
    """Replaces create_final_name — no fuzz, just direct comparison"""
    if len(full_name) == 1:
        return surname
    initials = []
    for n in full_name:
        term, _ = get_best_term(normalize_string(n), ss)
        if fuzz.ratio(term, surname) < 80:
            initials.append(term[0] if term else n[0])
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


def pipeline(name: str, ss, raw, id, description, col13):
    global total_distinct_names
    global merged_names_count
    total_distinct_names += 1

    splited_name = split_name(name)
    # first_last = get_first_and_last_name(splited_name)
    # surname = get_surname(first_last, ss)
    surname = get_surname(splited_name, ss)
    if surname is None:
        return
    key = create_key(splited_name, surname, ss)
    if key not in results:
        results[key] = {"original_name": [name], "full_name": [raw], "best_id": id, "all_ids": {id} , "description": max(description, col13)}
        return

    if name in results[key]["original_name"]:
        results[key]["all_ids"].add(id)
        if max(description, col13) > results[key]["description"]:
            results[key]["description"] = max(description, col13, results[key]["description"])
            results[key]['best_id'] = id
        if raw not in results[key]['full_name']:
            results[key]['full_name'].append(raw)
            # results[key]["all_ids"].append(id)
        return

    if all(same_person(name, existing) for existing in results[key]["original_name"]):
        merged_names_count += 1
        results[key]["original_name"].append(name)
        results[key]["all_ids"].add(id)
        if max(description, col13) > results[key]["description"]:
            results[key]["best_id"] = id
            results[key]["description"] = max(description, col13)
        if raw not in results[key]['full_name']:
            results[key]['full_name'].append(raw)
            # results[key]["all_ids"].append(id)

    else:
        full_key = create_full_key(splited_name, surname, ss)
        if full_key == key:
            clean_fallback_name = strip_nested_parentheses(name).lower().strip()
            full_key = f"{key} ({clean_fallback_name})"
        if full_key not in results:
            results[full_key] = {"original_name": [name], "full_name": [raw], "best_id": id, "all_ids": {id} , "description": max(description, col13)}
        elif name not in results[full_key]["original_name"]:
            merged_names_count += 1
            results[full_key]["original_name"].append(name)
            results[full_key]["full_name"].append(raw)
            results[full_key]["all_ids"].add(id)
            if max(description, col13) > results[full_key]["description"]:
                results[full_key]["description"] = max(description, col13)
                results[full_key]["best_id"] = id


if __name__ == "__main__":
    from itertools import islice
    import time
    start = time.time()

    total_count_full = 0

    ss = get_sym_spell()
    # with open("author_DB_names.txt", "r", encoding="utf-8") as d:
    #     names = json.load(d)
    i = 0
    # names = ["Philippe Daure"]
    get_df()
    # build_name_index()
    names = _df['name'].fillna('')
    ids = _df['id'].fillna('')
    descriptions = _df['description'].fillna('')
    col13 = _df['col13'].fillna('')
    for raw, id, description, col13 in zip(names, ids, descriptions, col13):
        total_count_full += 1
        i +=1
        print(i)
        people = split_people(raw)
        for person in people:
            pipeline(person, ss, raw, id, description, col13)

    num_final_keys = len(results)
    merged_names_count = total_distinct_names - num_final_keys

    # Meaningful metrics
    reduction_percentage = (merged_names_count / total_distinct_names) * 100 if total_distinct_names > 0 else 0
    avg_records_per_entity = total_distinct_names / num_final_keys if num_final_keys > 0 else 0

    output = {
        "total_raw_rows": int(total_count_full),
        "total_author_records": int(total_distinct_names),
        "unique_authors_found": int(num_final_keys),
        "total_merges_performed": int(merged_names_count),
        "reduction_percentage": f"{reduction_percentage:.2f}%",
        "avg_names_per_author": round(avg_records_per_entity, 2),
        # "merger_ratio_legacy": float(total_distinct_names / merged_names_count) if merged_names_count else 0,
    }

    for key, data in results.items():
        data["all_ids"] = list(data["all_ids"])
    def sort_json(obj):
        if isinstance(obj, dict):
            return {k: sort_json(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [sort_json(item) for item in obj]
        return obj

    sorted_results = sort_json(results)
    # with open("data.jsonl", "w") as f:
    #     for key, data in results.items():
    #         f.write(json.dumps({key: data}) + "\n")
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(sorted_results, f, indent=2, ensure_ascii=False)
    with open("output_numbers.json", "w", encoding="utf-8") as d:
        json.dump(output, d, indent=2, ensure_ascii=False)


    print(f"Execution time: {time.time() - start:.2f} seconds")