#FROM python:3.11-slim
#
#WORKDIR /app
#
#COPY requirements.txt .
#RUN pip install --no-cache-dir -r requirements.txt
##RUN --mount=type=cache,target=/root/.cache/pip \
##    pip install torch --index-url https://download.pytorch.org/whl/cpu && \
##    pip install -r requirements.txt
#
#COPY index_original_dictionary.py .
#COPY ps_supplier/csv.txt ps_supplier/csv.txt
#
#RUN mkdir -p /app/ps_supplier && \
#    SYMSPELL_INDEX_PATH=/app/ps_supplier/symspell_index.pickle python index_original_dictionary.py
#
#COPY . .
#

FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt