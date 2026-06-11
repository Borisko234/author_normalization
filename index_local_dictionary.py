import pandas as pd
import argparse
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="ps_supplier/ps_supplier.csv", help="Input CSV path")
    parser.add_argument("--output", default="ps_supplier/ps_supplier.pkl", help="Output Pickle path")
    args = parser.parse_args()

    print(f"Loading CSV from {args.input}...")
    df = pd.read_csv(args.input, sep=';', on_bad_lines='warn', low_memory=False, 
                     names=['id', 'name', 'normalized_name', 'created_at', 'updated_at', 
                            'active', 'code', 'first_name', 'last_name', 'birth_year', 
                            'death_year', 'description', 'col13', 'col14', 'col15', 
                            'col16', 'col17'])
    
    print(f"Saving to Pickle at {args.output}...")
    df.to_pickle(args.output)
    print("Done.")

if __name__ == "__main__":
    main()
