import os
import importlib.resources as resources
from symspellpy import SymSpell, Verbosity

from itertools import islice


_sym_spell = None
# Permanent location for the index
PICKLE_PATH = os.environ.get("SYMSPELL_INDEX_PATH", "ps_supplier/symspell_index.pickle")
# PICKLE_PATH = "ps_supplier/symspell_index_manufacturer.pickle"

def get_sym_spell():
    global _sym_spell
    if _sym_spell is None:
        # Pre author names, it's better to use a smaller distance or check prefix
        _sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        
        if os.path.exists(PICKLE_PATH):
            print(f"Loading SymSpell index from {PICKLE_PATH}")
            _sym_spell.load_pickle(PICKLE_PATH)
        else:
            print(f"Index not found at {PICKLE_PATH}. Creating from {os.path.abspath('ps_supplier/csv.txt')}")
            if os.path.exists("ps_supplier/csv.txt"):
                _sym_spell.create_dictionary("ps_supplier/csv.txt")
                _sym_spell.save_pickle(PICKLE_PATH)

            # for manufacturers
            # if os.path.exists("ps_manufacturers_csv.txt"):
            #     _sym_spell.create_dictionary("ps_manufacturers_csv.txt")
            #     _sym_spell.save_pickle(PICKLE_PATH)
    return _sym_spell

if __name__ == "__main__":
    # This block runs when Docker starts or during 'RUN' in Dockerfile
    get_sym_spell()
    print(f"SymSpell index created and saved to {PICKLE_PATH}")


# def main():
#     get_sym_spell()
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--output", default="symspell_index.pickle", help="Output path for the pickle file")
    # args = parser.parse_args()
    #
    # # Initialize
    # sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    # dictionary_path = resources.files("symspellpy") / "frequency_dictionary_en_82_765.txt"
    # sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1)
    #
    # # Save to the specified path
    # sym_spell.save_pickle(args.output)



if __name__ == "__main__":
    get_sym_spell()