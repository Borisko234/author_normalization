import dedupe
from itertools import islice
import pandas as pd
import os
import csv
from query import split_people, normalize_string, get_best_term, get_first_and_last_name, split_name
from index_original_dictionary import get_sym_spell


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
            usecols=['id', 'name', 'first_name', 'last_name'],
            dtype={'name': str},
            low_memory=False,
            nrows=2
        )
    return _df

def get_surname_firstname(names: list, ss, first_name=False) -> str:
    if not names:
        return "unknown"

    clean_names = names

    if first_name:
        worst_count = float('-inf')
    else:
        worst_count = float('inf')

    surname = None

    for name in clean_names:

        name_clean = normalize_string(name)
        other_parts = tuple(n for n in clean_names if n != name)
        if len(name) <= 1:
            continue
        if name.isnumeric():
            continue
        term, count = get_best_term(name_clean, ss, other_parts)

        if term is None or term.strip() in ['', '-']:
            term = name_clean
            count = 1

        if first_name:
            if count > worst_count:
                worst_count = count
                surname = term
        else:
            if count < worst_count:
                worst_count = count
                surname = term

    return surname if (surname and surname.strip() not in ['', '-']) else names[0]





if __name__ == "__main__":
    ss = get_sym_spell()

    _df = get_df()
    _df['name_list'] = _df['name'].fillna('').apply(split_people)
    _df['raw_full_name'] = _df['name']

    _df = _df.explode('name_list').reset_index(drop=True)
    _df = _df.rename(columns={'name_list': 'person_name'})

    _df = _df[_df['person_name'].astype(str).str.strip() != '']

    _df['last_name'] = _df['person_name'].apply(
        lambda name: get_surname_firstname(get_first_and_last_name(split_name(name)), ss, first_name=False))
    _df['first_name'] = _df['person_name'].apply(
        lambda name: get_surname_firstname(get_first_and_last_name(split_name(name)), ss, first_name=True))

    for col in ['first_name', 'last_name']:
        _df[col] = _df[col].astype(str).str.strip().str.lower()

    _df['id'] = _df.index
    data_d = {}
    # for row in islice(df.dropna().itertuples(), 10):
    #     data_d[row.id] = {'name': row.name.strip().strip('"').strip("'").lower().strip(), 'first_name': row.first_name.strip().strip('"').strip("'").lower().strip(), 'last_name': row.last_name.strip().strip('"').strip("'").lower().strip()}
    #     print(data_d[row.id])

    fields = [
        dedupe.variables.String('name'),
        dedupe.variables.String('first_name'),
        dedupe.variables.String('last_name')
    ]
    data_d = _df.set_index('id')[['name', 'first_name', 'last_name']].to_dict('index')

    deduper = dedupe.Dedupe(fields)
    if os.path.exists('dedupe_training.json'):
        with open('dedupe_training.json') as f:
            deduper.prepare_training(data_d, training_file=f)
    else:
        deduper.prepare_training(data_d)



    print("starting active labeling...")

    dedupe.console_label(deduper)


    with open("dedupe_training.json", "w") as tf:
        deduper.write_training(tf)

    print("clustering...")
    clustered_dupes = deduper.partition(data_d, 0.5)

    print("# duplicate sets", len(clustered_dupes))


    cluster_membership = {}
    for cluster_id, (records, scores) in enumerate(clustered_dupes):
        for record_id, score in zip(records, scores):
            cluster_membership[record_id] = {
                "Cluster ID": cluster_id,
                "confidence_score": score,
            }

    with open("deduplicated_authors.json", "w", encoding="utf-8") as f_output, open("ps_supplier/ps_supplier.csv", "r", encoding="utf-8") as f_input:
        reader = csv.DictReader(f_input)
        fieldnames = ["Cluster ID", "confidence_score"] + reader.fieldnames

        writer = csv.DictWriter(f_output, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            row_id = int(row["Id"])
            row.get(cluster_membership[row_id])
            print(row)
            # writer.writerow(row)

