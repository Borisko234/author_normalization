FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Don't COPY . . here if you're using volumes for dev
COPY . .

# Create a data directory and pre-generate the index
RUN mkdir -p /var/lib/symspell_data && \
    SYMSPELL_INDEX_PATH=/app/ps_supplier/symspell_index.pickle python index_original_dictionary.py

# CMD ["python", "app/query_edited.py"]