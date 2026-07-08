import duckdb
import splink.comparison_library as cl
from splink import  DuckDBAPI, Linker, SettingsCreator
import pandas as pd

from app.query import create_key, create_full_key
from index_original_dictionary import get_sym_spell
import json



from query import split_people, normalize_string, get_best_term, get_first_and_last_name, split_name


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
            # nrows=10000
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



ss = get_sym_spell()


print("<---getting DB--->")
_df = get_df()
_df = _df.dropna(subset=['name'])

total_count_full = len(_df)
merged_names_count = 0

_df = _df.rename(columns={'id': 'unique_id'})

_df['name_list'] = _df['name'].fillna('').apply(split_people)
_df['raw_full_name'] = _df['name']


_df = _df.explode('name_list').reset_index(drop=True)
_df = _df.rename(columns={'name_list': 'person_name'})


_df = _df[_df['person_name'].astype(str).str.strip() != '']
_df = _df[~_df['person_name'].astype(str).isin(['None', 'nan', '', 'null'])]

_df['last_name'] = _df['person_name'].apply(lambda name: get_surname_firstname(get_first_and_last_name(split_name(name)), ss, first_name=False))
_df['first_name'] = _df['person_name'].apply(lambda name: get_surname_firstname(get_first_and_last_name(split_name(name)), ss, first_name=True))

_df['name_sorted'] = _df['person_name'].apply(lambda x: " ".join(sorted(str(x).lower().split())))

_df = _df[~_df['last_name'].astype(str).isin(['None', 'nan', 'null', 'unknown'])]
_df = _df[~_df['first_name'].astype(str).isin(['None', 'nan', 'null', 'unknown'])]


for col in ['first_name', 'last_name']:
    _df[col] = _df[col].astype(str).str.strip().str.lower()

_df['unique_id'] = _df.index

total_distinct_names = len(_df)

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
        cl.ExactMatch("name_sorted"),
        cl.JaroWinklerAtThresholds("person_name")
    ],
    blocking_rules_to_generate_predictions=[
        "l.last_name = r.last_name and substring(l.first_name, 1, 2) = substring(r.first_name, 1, 2)",
        "l.first_name = r.first_name and substring(l.last_name, 1, 2) = substring(r.last_name, 1, 2)",
        "l.name_sorted = r.name_sorted"
    ],
)

linker = Linker(_df, settings, db_api=db_api)
print("done DB")

linker.training.estimate_probability_two_random_records_match(
    ["l.first_name = r.first_name and l.last_name = r.last_name"], recall=0.7
)
print(1)
linker.training.estimate_u_using_random_sampling(max_pairs=1e6)
print(2)
linker.training.estimate_parameters_using_expectation_maximisation("l.last_name = r.last_name and substring(l.first_name, 1, 2) = substring(r.first_name, 1, 2)")
print(3)
linker.training.estimate_parameters_using_expectation_maximisation("l.first_name = r.first_name and substring(l.last_name, 1, 2) = substring(r.last_name, 1, 2)")
print(4)
linker.training.estimate_parameters_using_expectation_maximisation("l.name_sorted = r.name_sorted")
print(5)

predictions = linker.inference.predict(threshold_match_probability=0.97)
clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(
    predictions, threshold_match_probability=0.97
)
clusters_df = clusters.as_pandas_dataframe()

print("clustering done, saving to json")

clustered_ids = set(clusters_df["unique_id"]) if not clusters_df.empty else set()
missing_df = _df[~_df["unique_id"].isin(clustered_ids)].copy()

max_cluster_id = clusters_df["cluster_id"].max() if not clusters_df.empty else 0
missing_df["cluster_id"] = range(int(max_cluster_id + 1), int(max_cluster_id + 1 + len(missing_df)))

missing_df["first_name_mode"] = missing_df["first_name"]
missing_df["last_name_mode"] = missing_df["last_name"]

full_output_df = pd.concat([clusters_df, missing_df], ignore_index=True)

modes = full_output_df.groupby("cluster_id")[["first_name", "last_name"]].agg(lambda x: x.mode()[0] if not x.mode().empty else 'unknown')
full_output_df = full_output_df.drop(columns=['first_name_mode', 'last_name_mode'], errors='ignore').merge(modes, on="cluster_id", suffixes=('', '_mode'))


full_output_df["split_person_name"] = full_output_df["person_name"].map(split_name)


print("only grouping left to do")
used_keys = {}
dict_keys = {}

for cluster_id, group in full_output_df.groupby("cluster_id", sort=True):


    row = group.iloc[0]

    short_key = create_key(
        row["split_person_name"],
        row["last_name_mode"],
        ss,
    )

    if short_key not in used_keys:
        used_keys[short_key] = cluster_id
        dict_keys[cluster_id] = short_key
    else:
        dict_keys[cluster_id] = create_full_key(
            row["split_person_name"],
            row["last_name_mode"],
            ss,
        )

full_output_df["dict_key"] = full_output_df["cluster_id"].map(dict_keys)


for _, group in full_output_df.groupby("dict_key"):
    merged_names_count += len(group) - 1

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
with open("splink_clusters_test.json", "w", encoding="utf-8") as f:
    json.dump(sorted_results, f, indent=2, ensure_ascii=False)



# Metrics calculation
num_final_keys = len(grouped)
merged_names_count = total_distinct_names - num_final_keys

# Meaningful metrics
reduction_percentage = (merged_names_count / total_distinct_names) * 100 if total_distinct_names > 0 else 0
avg_records_per_entity = total_distinct_names / num_final_keys if num_final_keys > 0 else 0

output_numbers = {
    "total_raw_rows": int(total_count_full),
    "total_author_records": int(total_distinct_names),
    "unique_authors_found": int(num_final_keys),
    "total_merges_performed": int(merged_names_count),
    "reduction_percentage": f"{reduction_percentage:.2f}%",
    "avg_names_per_author": round(avg_records_per_entity, 2),
    # "merger_ratio_legacy": float(total_distinct_names / merged_names_count) if merged_names_count else 0,
}


with open("splink_numbers_test.json", "w", encoding="utf-8") as f:
    json.dump(output_numbers, f, indent=2, ensure_ascii=False)

print("SUCCESS: Full database processed into JSON output.")
print("SUCCESS: Numerical metrics saved to output_numbers_splink.json for comparison.")