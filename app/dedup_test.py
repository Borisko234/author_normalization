import csv
import logging
import optparse
import os
import re
import json
import dedupe
from anyio.itertools import islice
from unidecode import unidecode
import pandas as pd

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
            usecols=['name', 'first_name', 'last_name'],
            dtype={'name': str},
            low_memory=False,
            nrows=2
        )
    return _df



if __name__ == "__main__":
    df = get_df()
    data_d = {}
    for row in islice(df.dropna().itertuples(), 10):
        data_d[row.index] = {'name': row.name.strip().strip('"').strip("'").lower().strip(), 'first_name': row.first_name.strip().strip('"').strip("'").lower().strip(), 'last_name': row.last_name.strip().strip('"').strip("'").lower().strip()}
        print(data_d[row.index])


    fields = [
        {'field': 'name', 'type': 'String', 'has missing': True},
        {'field': 'first_name', 'type': 'String', 'has missing': True},
        {'field': 'last_name', 'type': 'String', 'has missing': True},
    ]

    print(data_d)
    print()
    print(fields)

    # deduper = dedupe.Dedupe(fields)
    #
    #
    # deduper.prepare_training(data_d)
    #
    #
    #
    # print("starting active labeling...")
    #
    # dedupe.console_label(deduper)
    #
    #
    # with open(training_file, "w") as tf:
    #     deduper.write_training(tf)
    #
    #
    # with open(settings_file, "wb") as sf:
    #     deduper.write_settings(sf)
    #
    #
    # print("clustering...")
    # clustered_dupes = deduper.partition(data_d, 0.5)
    #
    # print("# duplicate sets", len(clustered_dupes))
    #
    #
    # cluster_membership = {}
    # for cluster_id, (records, scores) in enumerate(clustered_dupes):
    #     for record_id, score in zip(records, scores):
    #         cluster_membership[record_id] = {
    #             "Cluster ID": cluster_id,
    #             "confidence_score": score,
    #         }
    #
    # with open(output_file, "w") as f_output, open(input_file) as f_input:
    #     reader = csv.DictReader(f_input)
    #     fieldnames = ["Cluster ID", "confidence_score"] + reader.fieldnames
    #
    #     writer = csv.DictWriter(f_output, fieldnames=fieldnames)
    #     writer.writeheader()
    #
    #     for row in reader:
    #         row_id = int(row["Id"])
    #         row.update(cluster_membership[row_id])
    #         writer.writerow(row)

