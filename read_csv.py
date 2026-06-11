import pandas as pd
import re

# Define the names for the columns since the CSV doesn't have a header row
column_names = ['id_manufacturer', 'name', 'date_add', 'date_upd',
                'active']

# Optimization: Only load the 'name' column (the 2nd column) to save RAM
df = pd.read_csv(
    "ps_manufacturer.csv",
    sep=";", 
    names=column_names, 
    usecols=['name'],
    dtype={'name': str},
    low_memory=False
)

if __name__ == "__main__":
    names = df['name'].fillna('')
    all_names = []
    for name in names:
        # clean_name = name.strip()
        # print(name)
        # if (name == '""' or not name or name == "nan"):
        #     continue
        parts = re.sub(r'\s*\(.*?\)', '', name)
        parts = re.split(r'[\s.,;()]+', name)
        for part in parts:
            all_names.append(part)

    all_names = " ".join(all_names)
    with open("ps_manufacturers_csv.txt", "w", encoding="utf-8") as f:
        f.write(all_names)