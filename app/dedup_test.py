import dedupe
import json
from itertools import islice
import pandas as pd
import os
import csv
from query import split_people, normalize_string, get_best_term, get_first_and_last_name, split_name, create_key, create_full_key
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
            # nrows=10000
        )
    return _df

# def get_surname_firstname(names: list, ss, first_name=False) -> str:
#     if not names:
#         return "unknown"
#
#     clean_names = names
#
#     if first_name:
#         worst_count = float('-inf')
#     else:
#         worst_count = float('inf')
#
#     surname = None
#
#     for name in clean_names:
#
#         name_clean = normalize_string(name)
#         other_parts = tuple(n for n in clean_names if n != name)
#         if len(name) <= 1:
#             continue
#         if name.isnumeric():
#             continue
#         term, count = get_best_term(name_clean, ss, other_parts)
#
#         if term is None or term.strip() in ['', '-']:
#             term = name_clean
#             count = 1
#
#         if first_name:
#             if count > worst_count:
#                 worst_count = count
#                 surname = term
#         else:
#             if count < worst_count:
#                 worst_count = count
#                 surname = term
#
#     return surname if (surname and surname.strip() not in ['', '-']) else names[0]


def get_surname_firstname(names: list, ss, first_name=False) -> str:
    if not names:
        return "unknown"
    if len(names) == 1:
        return names[0]

    first_last_names = [names[0], names[-1]]
    clean_names = names


    if first_name:
        worst_count = float('-inf')
    else:
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
    import logging

    logging.getLogger('dedupe').setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)

    _df = get_df()
    _df['name_list'] = _df['name'].fillna('').apply(split_people)
    _df['raw_full_name'] = _df['name'].fillna('')

    _df = _df.explode('name_list').reset_index(drop=True)
    _df = _df.rename(columns={'name_list': 'person_name'})

    _df['person_name'] = _df['person_name'].fillna('').astype(str)
    _df = _df[_df['person_name'].str.strip() != '']

    _df['last_name'] = _df['person_name'].apply(
        lambda name: get_surname_firstname(split_name(name), ss, first_name=False)
    )
    _df['first_name'] = _df['person_name'].apply(
        lambda name: get_surname_firstname(split_name(name), ss, first_name=True)
    )

    for col in ['first_name', 'last_name']:
        _df[col] = _df[col].fillna('').astype(str).str.strip().str.lower()

    _df['id'] = _df.index
    data_d = {}


    fields = [
        dedupe.variables.String('name'),
        dedupe.variables.String('first_name'),
        dedupe.variables.String('last_name')
    ]
    data_d = _df.set_index('id')[['name', 'first_name', 'last_name']].to_dict('index')

    deduper = dedupe.Dedupe(fields)
    # if os.path.exists('dedupe_training.json'):
    with open('dedupe_training.json') as f:
        deduper.prepare_training(data_d, training_file=f)  # fast — only indexes the sample
    deduper.train()




    print("starting active labeling...")

    # dedupe.console_label(deduper)
    #
    # deduper.train()

    # with open("dedupe_training.json", "w") as tf:
    #     deduper.write_training(tf)

    print("clustering...")
    clustered_dupes = deduper.partition(data_d, 0.5)

    print("# duplicate sets", len(clustered_dupes))
    print("---------------------------------------------------------------------------------")

    cluster_rows = []
    for cluster_id, (records, scores) in enumerate(clustered_dupes):
        for record_id in records:
            cluster_rows.append({"unique_id": record_id, "cluster_id": cluster_id})

    clusters_df = pd.DataFrame(cluster_rows)

    # Records dedupe didn't cluster with anything become singleton clusters,
    # same as splink's missing_df handling
    clustered_ids = set(clusters_df["unique_id"]) if not clusters_df.empty else set()
    all_ids = set(_df["id"])
    missing_ids = all_ids - clustered_ids

    max_cluster_id = clusters_df["cluster_id"].max() if not clusters_df.empty else -1
    missing_rows = [
        {"unique_id": rid, "cluster_id": max_cluster_id + 1 + i}
        for i, rid in enumerate(sorted(missing_ids))
    ]
    missing_df = pd.DataFrame(missing_rows)

    full_output_df = pd.concat([clusters_df, missing_df], ignore_index=True)

    # Bring back the actual name fields via the id
    full_output_df = full_output_df.merge(
        _df[["id", "person_name", "raw_full_name", "first_name", "last_name"]],
        left_on="unique_id", right_on="id", how="left"
    )

    # Mode of first_name/last_name per cluster
    modes = full_output_df.groupby("cluster_id")[["first_name", "last_name"]].agg(
        lambda x: x.mode()[0] if not x.mode().empty else 'unknown'
    )
    full_output_df = full_output_df.drop(columns=['first_name', 'last_name']).merge(
        modes, on="cluster_id"
    ).rename(columns={"first_name": "first_name_mode", "last_name": "last_name_mode"})

    full_output_df["split_person_name"] = full_output_df["person_name"].map(split_name)

    print("only grouping left to do")
    used_keys = {}
    dict_keys = {}

    for cluster_id, group in full_output_df.groupby("cluster_id", sort=True):
        row = group.iloc[0]

        short_key = create_key(row["split_person_name"], row["last_name_mode"], ss)

        if short_key not in used_keys:
            used_keys[short_key] = cluster_id
            dict_keys[cluster_id] = short_key
        else:
            dict_keys[cluster_id] = create_full_key(row["split_person_name"], row["last_name_mode"], ss)

    full_output_df["dict_key"] = full_output_df["cluster_id"].map(dict_keys)

    grouped = (
        full_output_df.groupby("dict_key")
        .agg({
            "person_name": lambda x: sorted(set(x)),
            "raw_full_name": lambda x: sorted(set(x))
        })
        .to_dict(orient="index")
    )

    output = {
        key: {
            "full name": value["raw_full_name"],
            "original_name": value["person_name"],
        }
        for key, value in grouped.items()
    }


    def sort_json(obj):
        if isinstance(obj, dict):
            return {k: sort_json(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [sort_json(item) for item in obj]
        return obj


    sorted_results = sort_json(output)
    with open("dedupe_clusters_test.json", "w", encoding="utf-8") as f:
        json.dump(sorted_results, f, indent=2, ensure_ascii=False)

    # Metrics, matching splink script
    total_distinct_names = len(_df)
    num_final_keys = len(grouped)
    merged_names_count = total_distinct_names - num_final_keys
    reduction_percentage = (merged_names_count / total_distinct_names) * 100 if total_distinct_names else 0
    avg_records_per_entity = total_distinct_names / num_final_keys if num_final_keys else 0

    output_numbers = {
        "total_author_records": int(total_distinct_names),
        "unique_authors_found": int(num_final_keys),
        "total_merges_performed": int(merged_names_count),
        "reduction_percentage": f"{reduction_percentage:.2f}%",
        "avg_names_per_author": round(avg_records_per_entity, 2),
    }

    with open("dedupe_numbers_test.json", "w", encoding="utf-8") as f:
        json.dump(output_numbers, f, indent=2, ensure_ascii=False)

    print("SUCCESS: dedupe results saved in same JSON format as splink output.")



