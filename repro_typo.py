import sys
import os

# Add current directory to path so we can import app.query
sys.path.append(os.getcwd())

from app.query import pipeline, results, get_sym_spell

def test_merge():
    # Pre-load symspell to avoid noise in output
    get_sym_spell()
    
    test_names = ["Pike Aprliynne", "Pike, Aprilynne"]
    
    print(f"Processing names: {test_names}")
    for name in test_names:
        pipeline(name)
    
    print("\nResults:")
    import json
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_merge()
