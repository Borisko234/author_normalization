import csv
import os
import re
import pandas as pd
import importlib
import importlib.resources as resources
import sys
import json

from symspellpy import Verbosity
from index_original_dictionary import get_sym_spell

# from read_csv import parts


# Lazy load DataFrame only when needed
_df = None
results = {}


def get_df():
    global _df
    if _df is None:
        filepath = "ps_manufacturer.csv"
        # filepath = "ps_supplier/ps_supplier.csv"

        # column_names = ['id', 'name', 'normalized_name', 'created_at', 'updated_at',
        #                 'active', 'code', 'first_name', 'last_name', 'birth_year',
        #                 'death_year', 'description', 'col13', 'col14', 'col15',
        #                 'col16', 'col17']
        column_names = ['id_manufacturer', 'name', 'date_add', 'date_upd',
                        'active']
        _df = pd.read_csv(
            filepath,
            sep=";",
            names=column_names,
            usecols=['name'],
            dtype={'name': str},
            low_memory=False
        )
    return _df


TITLES = {
    'mgr.', 'mgr', 'ing.', 'ing', 'bc.', 'bc', 'doc.', 'doc', 'prof.', 'prof',
    'phdr.', 'phdr', 'rndr.', 'rndr', 'mudr.', 'mudr', 'mvdr.', 'mvdr', 'judr.', 'judr',
    'thdr.', 'thdr', 'paeddr.', 'paeddr', 'dr.', 'dr', 'ph.d.', 'ph.d',
}

LEGAL_FORMS = {
    's.r.o.', 'as', 'a.s.', 'spol', 's.p.o.', 'o.p.s.', 'z.s.', 'v.o.s.', 'k.s.',
    'inc.', 'ltd.', 'gmbh', 's. r. o.', 'a. s.', 'spol. s r.o.', 'v. o. s.',
    'k. s.', 'o. p. s.'
}

PUBLISHING_WORDS = {
    'nakladatelství', 'vydavatelství', 'publishing', 'ná'
}

GENERIC_WORDS = TITLES | LEGAL_FORMS | PUBLISHING_WORDS | {'co', 'and', 'a', 'so'}


def split_name(name):
    # Remove content within parentheses (including the parentheses themselves)
    name = re.sub(r'\(.*?\)', ' ', name)
    
    # Normalize spaces and lower case
    name = name.lower().strip()
    
    # Identify common legal forms and temporarily replace them to protect them from splitting
    protected = {
        's.r.o.': '###SRO###',
        's. r. o.': '###SRO###',
        'a.s.': '###AS###',
        'a. s.': '###AS###',
        'spol. s r.o.': '###SPOLSRV###',
        'v.o.s.': '###VOS###',
        'k.s.': '###KS###',
        'o.p.s.': '###OPS###',
        'as': '###AS_PLAIN###',
    }
    
    for key, val in protected.items():
        name = name.replace(key, val)
    
    # Split by common delimiters
    parts = re.split(r'[\s,-]+', name)
    
    # Restore protected forms
    reversed_protected = {v: k for k, v in protected.items()}
    final_parts = []
    for p in parts:
        if p in reversed_protected:
            final_parts.append(reversed_protected[p])
        elif p:
            final_parts.append(p)
            
    return final_parts


def split_people(name: str) -> list[str]:
    return [n.strip() for n in name.split(";") if n.strip()]


def get_first_and_last_name(name: list):
    if len(name) < 2:
        return name
    return [name[0], name[-1]]


def normalize_string(string):
    if len(string) == 2 and string.isupper():
        return string[0].strip().lower() + " " + string[1].strip().lower()
    return string.strip().lower()


def correct_text(raw_input: str) -> str:
    ss = get_sym_spell()
    results = ss.lookup(raw_input, Verbosity.CLOSEST, max_edit_distance=2)
    if len(results) <= 0:
        return "Not in database, do you want to use an AI for this?"
    return results[0].term if results else raw_input


def get_surname(names: list, typo: bool):
    ss = get_sym_spell()
    min_count = float('inf')
    surname = None
    
    # Separate generic and specific words
    specific_words = [n for n in names if normalize_string(n) not in GENERIC_WORDS]
    
    # If we have specific words, only consider them. Otherwise, consider all.
    search_list = specific_words if specific_words else names
    
    results = []
    for name in search_list:
        if len(name) <= 1:
            continue

        # O(1) Lookup with SymSpell
        name_norm = normalize_string(name)
        if not typo:
            results = ss.lookup(name_norm, Verbosity.CLOSEST, max_edit_distance=0)
        else:
            results = ss.lookup(name_norm, Verbosity.CLOSEST, max_edit_distance=2)

        if not results:
            # If not in dictionary, we treat it as potentially a very rare word (good for surname)
            # but only if it's not generic. 
            # If it's specific and not in dict, count is effectively 0 or 1.
            count = 0 
        else:
            count = results[0].count

        if min_count > count:
            min_count = count
            surname = name_norm
            
    return surname


def create_final_name(full_name: list, surname: str):
    parts = []
    surname = normalize_string(surname)
    for name in full_name:
        name_norm = normalize_string(name)
        if name_norm == surname:
            continue
            
        if name_norm in TITLES:
            continue
            
        if name_norm in LEGAL_FORMS:
            parts.append(name_norm.replace(' ', ''))
        elif name_norm in PUBLISHING_WORDS:
            parts.append(name_norm[0])
        else:
            parts.append(name_norm[0])
            
    return f"{surname} {' '.join(parts)}".strip()


def create_full_final_name(full_name: list, surname: str):
    return f"{surname} {' '.join(full_name)}"


def normalize_order(name: str) -> list[str]:
    """Remove punctuation, split, sort alphabetically so order doesn't matter."""
    # Split by whitespace, comma, dot, or hyphen
    parts = re.split(r'[\s,.\-]+', name.strip().lower())
    parts = [p.strip() for p in parts if p.strip()]
    return sorted(parts)


def to_initials_sorted(name: str) -> list[str]:
    parts = normalize_order(name)
    result = []
    for part in parts:
        if '.' in part:
            result.extend(p for p in part.split('.') if p)
        else:
            result.append(part[0])
    return sorted(result)


def is_consistent(name1: str, name2: str) -> bool:
    parts1 = normalize_order(name1)
    parts2 = normalize_order(name2)

    if len(parts1) != len(parts2):
        return False

    for p1, p2 in zip(parts1, parts2):
        if len(p1) > 1 and len(p2) > 1:
            if p1 != p2:
                # Check if one is a prefix of another (at least 3 chars) to handle truncations
                if (p1.startswith(p2) and len(p2) >= 3) or (p2.startswith(p1) and len(p1) >= 3):
                    continue
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


def pipeline(name: str):
    final_name = ""
    splited_name = split_name(name)
    # first_last = get_first_and_last_name(splited_name)
    # surname = get_surname(first_last, False)

    # for manufacturer
    surname = get_surname(splited_name, False)

    if surname is None:
        # for manufacturer
        surname = get_surname(splited_name, True)

        # surname = get_surname(first_last, True)
        if surname is None:
            print(f"invalid name for {name}")
            return
        else:
            final_name = create_final_name(splited_name, surname)
    else:
        final_name = create_final_name(splited_name, surname)
        print(final_name)
    print(splited_name)
    print(surname)
    if results.get(final_name) is None:
        results[final_name] = {
            "original_name": [name],
            "books": []
        }
    else:
        if name in results[final_name]["original_name"]:
            return
        else:
            if same_person(name, results[final_name]["original_name"][0]):
                results[final_name]["original_name"].append(name)
            else:
                full_name = create_full_final_name(splited_name, surname)
                results[full_name] = {
                    "original_name": [name],
                    "books": []
                }


if __name__ == "__main__":
    from itertools import islice
    import time

    start = time.time()
    results = {}
    # names = ["EUROMEDIA GROUP, k.s. (KK)", "Albatros (Media) a.s."]
    get_df()
    names = _df['name'].fillna('')
    for raw in names:
        # print(1)
        people = split_people(raw)
        # print(people)
        for person in people:
            # print(person)
            pipeline(person)

    with open("output_manufacturer.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # name = "Nakladatelství DONA s.r.o."
    # splited_name = split_name(name)
    # print(splited_name)
    # final_name = get_surname(splited_name, False)
    # print(final_name)



    print(f"Execution time: {time.time() - start:.2f} seconds")
