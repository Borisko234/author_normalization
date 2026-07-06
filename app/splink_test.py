import duckdb
import splink.comparison_library as cl
from splink import  DuckDBAPI, Linker, SettingsCreator
import pandas as pd
import re

from app.query import create_key, create_full_key
from index_original_dictionary import get_sym_spell
import json



from query import split_people, normalize_string, get_best_term, get_first_and_last_name


_df = None
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
            nrows=9000
        )
    return _df


settings = SettingsCreator(
    link_type="dedupe_only",
    comparisons=[
        cl.NameComparison("first_name"),
        cl.NameComparison("last_name"),
    ],
    blocking_rules_to_generate_predictions=[
        "l.last_name = r.last_name",
    ],
)

# def get_surname_firstname(names: tuple, ss, first_name=False) -> str | None:
#     if first_name:
#         worst_count = float('-inf')
#     else:
#         worst_count = float('inf')
#     surname = None
#
#     for name in names:
#         if len(name) <= 1:
#             continue
#         name = normalize_string(name)
#         other_parts = tuple(n for n in names if n != name)
#         term, count = get_best_term(name, ss, other_parts)
#         if term is None:
#             continue
#         if first_name:
#             if count > worst_count:
#                 worst_count = count
#                 surname = term
#         else:
#             if count < worst_count:
#                 worst_count = count
#                 surname = term
#
#     return surname

def split_name(name):
    name = str(name)
    # Remove anything inside parentheses or quotes completely
    name = re.sub(r'<<|>>', ' ', name)
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'"[^"]*"', '', name)
    name = re.sub(r'\'[^\']*\'', '', name)

    parts = re.split(r'[\s.,:\-]+', name.lower().strip())
    return [p for p in parts if p]

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

        term, count = get_best_term(name_clean, ss, other_parts)

        # FIX: Instead of dropping the word, fall back directly to the raw text item
        if term is None or term.strip() in ['', '-']:
            term = name_clean
            count = 1  # Standard base frequency allocation

        if first_name:
            if count > worst_count:
                worst_count = count
                surname = term
        else:
            if count < worst_count:
                worst_count = count
                surname = term

    return surname if (surname and surname.strip() not in ['', '-']) else names[0]



ss = get_sym_spell()

print("<---getting DB--->")
_df = get_df()
_df = _df.dropna(subset=['name'])
_df = _df.rename(columns={'id': 'unique_id'})

# 1. Split multi-person cells into lists
_df['name_list'] = _df['name'].fillna('').apply(split_people)
_df['raw_full_name'] = _df['name']

# 2. Explode: one row per person
_df = _df.explode('name_list').reset_index(drop=True)
_df = _df.rename(columns={'name_list': 'person_name'})

# Filter out pure blank lines
_df = _df[_df['person_name'].astype(str).str.strip() != '']

# 3. Parse names into normalized tokens (No dropping!)
_df['last_name'] = _df['person_name'].apply(lambda name: get_surname_firstname(get_first_and_last_name(split_name(name)), ss, first_name=False))
_df['first_name'] = _df['person_name'].apply(lambda name: get_surname_firstname(get_first_and_last_name(split_name(name)), ss, first_name=True))

for col in ['first_name', 'last_name']:
    _df[col] = _df[col].astype(str).str.strip().str.lower()

# Ensure we always have valid unique IDs matching index space
_df['unique_id'] = _df.index

# 4. DuckDB setup
con = duckdb.connect()
con.execute("SET threads = 3;")
con.execute("SET max_memory = '6GB';")
con.execute("SET temp_directory = '/tmp/duckdb';")
db_api = DuckDBAPI(connection=con)

settings = SettingsCreator(
    link_type="dedupe_only",
    comparisons=[
        cl.NameComparison("first_name"),
        cl.NameComparison("last_name"),
    ],
    blocking_rules_to_generate_predictions=[
        "l.last_name = r.last_name",
        "l.first_name = r.first_name"
    ],
)

linker = Linker(_df, settings, db_api=db_api)
print("done DB")

# Estimate parameters unsupervised
linker.training.estimate_probability_two_random_records_match(
    ["l.first_name = r.first_name and l.last_name = r.last_name"], recall=0.7
)
print(1)
linker.training.estimate_u_using_random_sampling(max_pairs=1e6)
print(2)
linker.training.estimate_parameters_using_expectation_maximisation("l.last_name = r.last_name")
print(3)
linker.training.estimate_parameters_using_expectation_maximisation("l.last_name = r.last_name")
print(4)

predictions = linker.inference.predict(threshold_match_probability=0.85)
clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(
    predictions, threshold_match_probability=0.85
)
clusters_df = clusters.as_pandas_dataframe()

print("clustering done, saving to json")

# 5. Bring back singletons (rows Splink dropped because they have no duplicates)
clustered_ids = set(clusters_df["unique_id"]) if not clusters_df.empty else set()
missing_df = _df[~_df["unique_id"].isin(clustered_ids)].copy()

# Provide unique IDs to separate un-clustered rows cleanly
max_cluster_id = clusters_df["cluster_id"].max() if not clusters_df.empty else 0
missing_df["cluster_id"] = range(int(max_cluster_id + 1), int(max_cluster_id + 1 + len(missing_df)))

missing_df["first_name_mode"] = missing_df["first_name"]
missing_df["last_name_mode"] = missing_df["last_name"]

# Combine into a unified schema table
full_output_df = pd.concat([clusters_df, missing_df], ignore_index=True)

modes = full_output_df.groupby("cluster_id")[["first_name", "last_name"]].agg(lambda x: x.mode()[0] if not x.mode().empty else 'unknown')
full_output_df = full_output_df.drop(columns=['first_name_mode', 'last_name_mode'], errors='ignore').merge(modes, on="cluster_id", suffixes=('', '_mode'))

# 6. Generate final target layout keys
initials = full_output_df["first_name_mode"].str.strip().str.get(0).str.lower().fillna('')
# full_output_df["dict_key"] = (full_output_df["last_name_mode"].str.strip().str.lower() + " " + initials).str.strip()
# direct_key = create_key(split_name(_df['name_list']), _df['last_name'], ss )
# if full_output_df[direct_key] is not None:
full_output_df["normalized_key"] = full_output_df.apply(
    lambda row: create_key(split_name(row['person_name']), row['last_name_mode'], ss),
    axis=1
)
# 2. Check if the normalized_key is shared by multiple rows
# keep=False marks ALL occurrences of a duplicate as True
is_duplicate = full_output_df.duplicated(subset=["normalized_key"], keep=False)

# 3. Create the final dict_key column based on that check
# If it's a duplicate, fall back to the full person_name. Otherwise, use the normalized key.
full_output_df["dict_key"] = full_output_df["normalized_key"] # Default to normalized

# Where duplicates exist, overwrite with the literal full name string
if is_duplicate.any():
    full_output_df.loc[is_duplicate, "dict_key"] = full_output_df[is_duplicate].apply(
        lambda row: create_full_key(split_name(row['person_name']), row['last_name_mode'], ss),
        axis=1
    )
print("only grouping left to do")
grouped = full_output_df.groupby("dict_key").agg({
    "person_name": lambda x: sorted(list(set(x))),
    "raw_full_name": lambda x: sorted(list(set(x)))
}).to_dict(orient="index")

output = {
    k: {
        "full name": v["raw_full_name"],
        "original_name": v["person_name"]
    }
    for k, v in grouped.items()
}

with open("splink_clusters.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print("SUCCESS: Full database processed into JSON output.")






# print("<---getting DB--->")
# _df = get_df()
# _df = _df.dropna(subset=['name'])
# _df = _df.rename(columns={'id': 'unique_id'})
#
# # 1. Split multi-person cells into lists
# _df['name_list'] = _df['name'].fillna('').apply(split_people)
# # _df['raw_full_name'] = _df['name']
#
# # 2. Explode: one row per person instead of one row per original cell
# _df = _df.explode('name_list').reset_index(drop=True)
# _df = _df.rename(columns={'name_list': 'person_name'})
#
# _df = _df[_df['person_name'].str.strip() != '']
#
# _df = _df[_df['person_name'].notna()]
# _df = _df[_df['person_name'].astype(str).str.strip() != '']
#
# garbage_pattern = r'[0-9/\(\)\d]|sborník|vydavatelství|edice'
# _df = _df[~_df['person_name'].str.lower().str.contains(garbage_pattern, regex=True, na=False)]
#
# _df['last_name'] = _df['person_name'].apply(lambda name: get_surname_firstname(split_name(name), ss, first_name=False))
# _df['first_name'] = _df['person_name'].apply(lambda name: get_surname_firstname(split_name(name), ss, first_name=True))
#
# for col in ['first_name', 'last_name']:
#     _df[col] = _df[col].astype(str).str.strip().str.lower()
#
# _df = _df[(_df['first_name'] != '-') & (_df['last_name'] != '-')]
# _df = _df[(_df['first_name'] != '') & (_df['last_name'] != '')]
#
# # 6. Unique id required by splink/dedupe
# _df['unique_id'] = _df.index
#
# # db_api = DuckDBAPI(
# #     connection_options={
# #         "threads": "3",               # Restrict to 4 CPU threads (adjust based on your CPU)
# #         "max_memory": "6GB",          # Cap memory usage so your desktop doesn't lock up
# #         "temp_directory": "/tmp/duckdb" # Spills safely to disk if it goes over RAM limits
# #     }
# # )
# con = duckdb.connect()
# con.execute("SET threads = 3;")
# con.execute("SET max_memory = '6GB';")
# con.execute("SET temp_directory = '/tmp/duckdb';")
#
# # 2. Pass that configured connection into Splink's DuckDBAPI
# db_api = DuckDBAPI(connection=con)
#
# settings = SettingsCreator(
#     link_type="dedupe_only",
#     comparisons=[
#         cl.NameComparison("first_name"),
#         cl.NameComparison("last_name"),
#     ],
#     # MUST HAVE: Limit predictions to records sharing at least some name details
#     blocking_rules_to_generate_predictions=[
#         "l.last_name = r.last_name",
#         "l.first_name = r.first_name"
#     ],
# )
#
# linker = Linker(_df, settings, db_api=db_api)
# print("done DB")
# # Estimate parameters unsupervised
# linker.training.estimate_probability_two_random_records_match(
#     ["l.first_name = r.first_name and l.last_name = r.last_name"], recall=0.7
# )
# print(1)
# linker.training.estimate_u_using_random_sampling(max_pairs=1e6)
# print(2)
# linker.training.estimate_parameters_using_expectation_maximisation(
#     "l.last_name = r.last_name"
# )
# print(3)
#
# linker.training.estimate_parameters_using_expectation_maximisation("l.last_name = r.last_name")
# print(4)
# predictions = linker.inference.predict(threshold_match_probability=0.85)
#
# clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(
#     predictions, threshold_match_probability=0.85
# )
# clusters_df = clusters.as_pandas_dataframe()
#
#
#
# print("clustering done, saving to json")
# import json
# from collections import defaultdict
#
# def make_key(first_name: str, last_name: str) -> str:
#     initial = first_name.strip()[0].lower() if first_name.strip() else ''
#     return f"{last_name.strip().lower()} {initial}".strip()
#
# output = defaultdict(lambda: {"original_name": [], "full name": []})
#
# modes = clusters_df.groupby("cluster_id")[["first_name", "last_name"]].agg(lambda x: x.mode()[0] if not x.mode().empty else '')
# print("modes done, saving to json")
#
# # Join the modes back to the main clusters dataframe
# clusters_df = clusters_df.merge(modes, on="cluster_id", suffixes=('', '_mode'))
# print("clusters_df done, saving to json")
#
# initials = clusters_df["first_name_mode"].str.strip().str.get(0).str.lower().fillna('')
# clusters_df["dict_key"] = (clusters_df["last_name_mode"].str.strip().str.lower() + " " + initials).str.strip()
# print("only grouping left to do")
#
# # grouped = clusters_df.groupby("dict_key").agg({
# #     "raw_full_name": list,
# #     "person_name": list
# # }).to_dict(orient="index")
#
# grouped = clusters_df.groupby("dict_key").agg({
#     "person_name": lambda x: sorted(list(set(x))),
#     # Optional: If you still need to see what raw input text generated this cluster,
#     # uncomment the line below to store unique raw source segments:
#     # "raw_full_name": lambda x: sorted(list(set(x)))
# }).to_dict(orient="index")
#
# # output = {k: {"original_name": v["raw_full_name"], "full name": v["person_name"]} for k, v in grouped.items()}
# output = {
#     k: {
#         "full name": v["person_name"],
#         "original_name": v["person_name"]  # Now mirrors your unique entity variations perfectly!
#     }
#     for k, v in grouped.items()
# }
# with open("splink_clusters.json", "w", encoding="utf-8") as f:
#     json.dump(output, f, indent=2, ensure_ascii=False)