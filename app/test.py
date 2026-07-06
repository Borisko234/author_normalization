if __name__ == "__main__":
    import os
    from itertools import islice
    i = 0
    import json
    missed_authors = {}
    with open("output_DB.json", "r", encoding="utf-8") as f:
        DB_authors = json.load(f)
    with open("output.json", "r", encoding="utf-8") as d:
        authors = json.load(d)
    for author in DB_authors:
        if author not in authors:
            i += 1
            # print(DB_authors[author])
            missed_authors[author] = DB_authors[author]
    print(f"number of missing authors : {i}")
    missed_authors["missed_authors"] = i
    with open("missed_authors_from_DB.json", "w", encoding="utf-8") as f:
        json.dump(missed_authors, f, indent=2, ensure_ascii=False)

    # print(f"number of isbn authors : {len(authors)}")
    # with open("raw_DB_names.txt", "r", encoding="utf-8") as f:
    #     authors = json.load(f)
    # print(f"number of all authors : {len(authors)}")

