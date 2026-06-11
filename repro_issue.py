from index_original_dictionary import get_sym_spell
from symspellpy import Verbosity

ss = get_sym_spell()
term = "Bell"
results = ss.lookup(term, Verbosity.ALL, max_edit_distance=0)

if results:
    for res in results:
        print(f"Term: {res.term}, Count: {res.count}, Distance: {res.distance}")
else:
    print(f"No results found for '{term}'")

# Also check if it's in the dictionary directly
print(f"Is '{term.lower()}' in dictionary? {term.lower() in ss.words}")
