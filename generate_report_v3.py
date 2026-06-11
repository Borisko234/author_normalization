import json
import pandas as pd
import os

def generate_report_v3():
    print("Loading output.json...")
    with open("output.json", "r", encoding="utf-8") as f:
        authors = json.load(f)

    print("Loading ps_supplier.csv...")
    supplier_cols = ['id', 'name', 'normalized_name', 'created_at', 'updated_at',
                    'active', 'code', 'first_name', 'last_name', 'birth_year',
                    'death_year', 'description', 'col13', 'col14', 'col15',
                    'col16', 'col17']
    df_supplier = pd.read_csv("ps_supplier/ps_supplier.csv", sep=";", names=supplier_cols, usecols=['id', 'name'], dtype=str, low_memory=False)
    
    print("Building name_to_id mapping...")
    df_supplier['name_clean'] = df_supplier['name'].str.strip().str.lower()
    name_to_id = df_supplier.dropna(subset=['name_clean']).set_index('name_clean')['id'].to_dict()
    del df_supplier

    print("Loading ps_product.csv...")
    # id_product is 1st column (index 0), id_supplier is 2nd column (index 1)
    df_product = pd.read_csv("ps_product.csv", names=['id_product', 'id_supplier'], usecols=[0, 1], dtype=str, low_memory=False, encoding_errors='replace')
    
    # Strip quotes if they exist in id_supplier
    df_product['id_supplier'] = df_product['id_supplier'].str.strip('"')
    
    supplier_to_products = df_product.groupby('id_supplier')['id_product'].apply(list).to_dict()

    print("Processing authors and books...")
    authors_data = []
    
    # Sort authors for consistency
    sorted_author_keys = sorted(authors.keys())

    for norm_name in sorted_author_keys:
        data = authors[norm_name]
        orig_names_with_books = []
        has_any_books = False
        
        for orig_name in data['original_name']:
            s_id = name_to_id.get(orig_name.strip().lower())
            books = []
            if s_id and s_id in supplier_to_products:
                books = sorted(supplier_to_products[s_id])
                has_any_books = True
            
            orig_names_with_books.append({
                "name": orig_name,
                "books": books
            })
        
        if has_any_books:
            authors_data.append({
                "normalized_name": norm_name,
                "original_names": orig_names_with_books
            })

    print(f"Total authors with books: {len(authors_data)}")
    
    # Split into chunks (e.g., 2000 authors per file)
    chunk_size = 2000
    import math
    total_chunks = math.ceil(len(authors_data) / chunk_size)
    
    # Define directories
    base_dir = "report_v5"
    parts_dir = os.path.join(base_dir, "parts")
    
    if not os.path.exists(parts_dir):
        os.makedirs(parts_dir)
    
    # Ensure directories are writable/deletable by everyone
    try:
        os.chmod(base_dir, 0o777)
        os.chmod(parts_dir, 0o777)
    except PermissionError:
        print(f"Warning: Could not change permissions for {base_dir}. Skipping chmod.")

    for i in range(total_chunks):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, len(authors_data))
        chunk = authors_data[start_idx:end_idx]
        
        filename = f"{parts_dir}/authors_report_part_{i+1}.html"
        print(f"Generating {filename}...")
        
        with open(filename, "w", encoding="utf-8") as f:
            header = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Author Normalization Report v3 - Part {i+1}</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; background-color: #f4f4f9; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        .search-container {{ position: sticky; top: 0; background: white; padding: 10px 0; border-bottom: 2px solid #eee; z-index: 100; }}
        #searchInput {{ width: 100%; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
        .author-card {{ border: 1px solid #ddd; border-radius: 8px; margin: 20px 0; padding: 15px; background: #fff; }}
        .author-name {{ font-size: 1.4em; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-bottom: 15px; }}
        .orig-name-section {{ margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 4px; }}
        .orig-name {{ font-weight: bold; color: #e67e22; margin-bottom: 10px; font-size: 1.1em; }}
        .books-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; }}
        .book {{ text-align: center; border: 1px solid #eee; padding: 8px; border-radius: 4px; transition: transform 0.2s; background: white; }}
        .book:hover {{ transform: scale(1.05); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .book img {{ width: 100%; height: auto; border-radius: 2px; display: block; margin-bottom: 5px; min-height: 150px; background: #eee; cursor: pointer; }}
        .book-id {{ font-size: 0.85em; color: #7f8c8d; }}
        .hidden {{ display: none; }}
        .stats {{ margin-top: 10px; color: #666; font-size: 0.9em; }}
        .nav {{ margin-bottom: 20px; display: flex; justify-content: space-between; }}
        .nav a {{ text-decoration: none; color: #3498db; font-weight: bold; }}

        /* Modal Styles */
        .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.9); cursor: zoom-out; }}
        .modal-content {{ margin: auto; display: block; max-width: 90%; max-height: 90%; margin-top: 5vh; box-shadow: 0 0 20px rgba(255,255,255,0.2); width: 20%;}}
        .modal-close {{ position: absolute; top: 15px; right: 35px; color: #f1f1f1; font-size: 40px; font-weight: bold; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Author Normalization Report - Part {i+1} of {total_chunks}</h1>
        <div class="nav">
"""
            f.write(header)

            if i > 0:
                f.write(f'<a href="authors_report_part_{i}.html">&laquo; Previous</a>')
            else:
                f.write('<span></span>')
            
            f.write(f'<a href="../index.html">Back to Index</a>')

            if i < total_chunks - 1:
                f.write(f'<a href="authors_report_part_{i+2}.html">Next &raquo;</a>')
            else:
                f.write('<span></span>')

            f.write("""
        </div>
        <div class="search-container">
            <input type="text" id="searchInput" placeholder="Search authors in this part..." onkeyup="filterAuthors()">
            <div class="stats" id="stats">Showing all authors in this part</div>
        </div>
        <div id="authorList">
""")
            
            for author in chunk:
                f.write(f'            <div class="author-card" data-name="{author["normalized_name"].lower()} {" ".join([on["name"].lower() for on in author["original_names"]])}">\n')
                f.write(f'                <div class="author-name">{author["normalized_name"]}</div>\n')
                
                for orig in author["original_names"]:
                    if not orig["books"]: continue
                    f.write(f'                <div class="orig-name-section">\n')
                    f.write(f'                    <div class="orig-name">Original: {orig["name"]}</div>\n')
                    f.write(f'                    <div class="books-grid">\n')
                    
                    for b_id in orig["books"]:
                        img_url = f"https://img-cloud.megaknihy.cz/{b_id}-category/7bb17d304530a6a2b81a63bd0fedef4c/odhaleni-michaela-jacksona-pribeh-ktery-jste-nikdy-neslyseli.webp"
                        f.write(f'                        <div class="book">\n')
                        f.write(f'                            <img data-src="{img_url}" alt="Book {b_id}" class="lazy" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=" onclick="openModal((this.dataset.src || this.src).replace(\'-category\', \'-large\'))">\n')
                        f.write(f'                            <div class="book-id">ID: {b_id}</div>\n')
                        f.write(f'                        </div>\n')
                    
                    f.write(f'                    </div>\n')
                    f.write(f'                </div>\n')
                f.write(f'            </div>\n')

            f.write("""
        </div>
    </div>

    <!-- Modal for enlarging images -->
    <div id="imageModal" class="modal" onclick="closeModal()">
        <span class="modal-close">&times;</span>
        <img class="modal-content" id="modalImg">
    </div>

    <script>
        function filterAuthors() {
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const cards = document.getElementsByClassName('author-card');
            let visibleCount = 0;
            let firstVisible = null;

            for (let i = 0; i < cards.length; i++) {
                const name = cards[i].getAttribute('data-name');
                if (name.includes(filter)) {
                    cards[i].classList.remove('hidden');
                    visibleCount++;
                    if (!firstVisible) firstVisible = cards[i];
                } else {
                    cards[i].classList.add('hidden');
                }
            }
            document.getElementById('stats').innerText = `Showing ${visibleCount} authors`;
            
            if (firstVisible && filter.length > 0) {
                firstVisible.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            lazyLoad();
        }

        // Auto-search from URL parameter
        window.addEventListener('load', () => {
            const params = new URLSearchParams(window.location.search);
            const search = params.get('search');
            if (search) {
                document.getElementById('searchInput').value = search;
                filterAuthors();
            }
        });

        function lazyLoad() {
            const lazyImages = document.querySelectorAll('img.lazy');
            const observer = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        observer.unobserve(img);
                    }
                });
            });

            lazyImages.forEach(img => observer.observe(img));
        }
        window.addEventListener('load', lazyLoad);

        function openModal(src) {
            const modal = document.getElementById("imageModal");
            const modalImg = document.getElementById("modalImg");
            modal.style.display = "block";
            modalImg.src = src;
        }

        function closeModal() {
            document.getElementById("imageModal").style.display = "none";
        }
    </script>
</body>
</html>
""")
        # Ensure files are editable by everyone
        try:
            os.chmod(filename, 0o666)
        except PermissionError:
            pass

    # Index file
    search_index = []
    # Only index authors that actually have original names (which should be all in authors_data)
    for i in range(total_chunks):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, len(authors_data))
        for author in authors_data[start_idx:end_idx]:
            # Store only essential data to keep index small
            # n: normalized name, p: part number
            # Using short keys to save space
            search_index.append({"n": author["normalized_name"], "p": i + 1})
    
    # Save search_index.json separately as requested
    print(f"Generating {base_dir}/search_index.json...")
    with open(f"{base_dir}/search_index.json", "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, separators=(',', ':'))
    try:
        os.chmod(f"{base_dir}/search_index.json", 0o666)
    except PermissionError:
        pass

    print(f"Generating {base_dir}/index.html (with embedded search index)...")
    with open(f"{base_dir}/index.html", "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Author Normalization Report Index v4</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-radius: 8px; }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        .search-section { background: #ebf5fb; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
        #globalSearch { width: 100%; padding: 15px; font-size: 18px; border: 2px solid #3498db; border-radius: 6px; box-sizing: border-box; }
        #results { margin-top: 10px; max-height: 400px; overflow-y: auto; border: 1px solid #ddd; background: white; border-radius: 4px; display: none; }
        .result-item { padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; }
        .result-item:hover { background: #f0f7fd; }
        .result-item .norm { font-weight: bold; color: #2c3e50; }
        .result-item .orig { font-size: 0.85em; color: #7f8c8d; display: block; }
        
        .parts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; list-style: none; padding: 0; }
        .part-item { background: #fff; border: 1px solid #eee; border-radius: 6px; transition: all 0.2s; }
        .part-item:hover { border-color: #3498db; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.05); }
        .part-item a { text-decoration: none; color: #3498db; display: block; padding: 15px; height: 100%; }
        .part-title { font-weight: bold; font-size: 1.1em; display: block; margin-bottom: 5px; }
        .part-meta { font-size: 0.85em; color: #95a5a6; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Author Normalization Report</h1>
        <p>Total Authors with Books: """ + str(len(authors_data)) + """</p>
        
        <div class="search-section">
            <h3>Quick Search (Global)</h3>
            <input type="text" id="globalSearch" placeholder="Type author name (normalized or original)..." autocomplete="off">
            <div id="results"></div>
        </div>

        <h3>Browse by Part</h3>
        <ul class="parts-grid">
""")
        for i in range(total_chunks):
            start_author = authors_data[i*chunk_size]['normalized_name']
            end_idx = min((i + 1) * chunk_size - 1, len(authors_data) - 1)
            end_author = authors_data[end_idx]['normalized_name']
            f.write(f"""
            <li class="part-item">
                <a href="parts/authors_report_part_{i+1}.html">
                    <span class="part-title">Part {i+1}</span>
                    <span class="part-meta">"{start_author}" &hellip; "{end_author}"</span>
                </a>
            </li>""")
        
        f.write("""
        </ul>
    </div>
""")
        f.write("""
            <script>
                const searchIndex = """)

        search_index_json = json.dumps(search_index, ensure_ascii=True, separators=(',', ':'))
        search_index_json = search_index_json.replace('</script>', '<\\/script>')
        f.write(search_index_json)

        f.write(""";
                console.log('Search index loaded:', searchIndex.length, 'authors');

                const searchInput = document.getElementById('globalSearch');
                const resultsDiv = document.getElementById('results');

                searchInput.addEventListener('input', () => {
                    const query = searchInput.value.toLowerCase().trim();
                    if (query.length < 2) {
                        resultsDiv.style.display = 'none';
                        return;
                    }

                    const filtered = [];
                    for (const item of searchIndex) {
                        if (item.n.toLowerCase().includes(query)) {
                            filtered.push(item);
                        }
                        if (filtered.length >= 50) break;
                    }

            if (filtered.length > 0) {
                resultsDiv.innerHTML = filtered.map(item => `
                    <div class="result-item" onclick="window.location.href='parts/authors_report_part_${item.p}.html?search=${encodeURIComponent(item.n)}'">
                        <span class="norm">${item.n}</span>
                    </div>
                `).join('');
                resultsDiv.style.display = 'block';
            } else {
                resultsDiv.innerHTML = '<div class="result-item">No authors found</div>';
                resultsDiv.style.display = 'block';
            }
        });

        // Hide results when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target !== searchInput && e.target !== resultsDiv) {
                resultsDiv.style.display = 'none';
            }
        });
    </script>
</body>
</html>
""")
    try:
        os.chmod(f"{base_dir}/index.html", 0o644)
    except PermissionError:
        pass

    print(f"Done! Reports generated in {base_dir} directory")

if __name__ == "__main__":
    generate_report_v3()
