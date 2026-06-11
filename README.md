### 🚀 Daily Pipeline

#### 1. Every morning (Start)
```bash
make up
```

#### 2. If you change code/requirements (Rebuild)
```bash
make build
```

#### 3. Run specific scripts
- **Normalization Query:**
  ```bash
  make query
  ```
- **Other scripts:**
  ```bash
  make run file=app/pandas_example.py
  ```

#### 4. Stop when finished
```bash
make down
```

---

### 📝 Cheat Sheet
| Task | Command |
| :--- | :--- |
| **Start Project** | `make up` |
| **Build/Rebuild** | `make build` |
| **Run query.py** | `make query` |
| **Run any script** | `make run file=path/to/file.py` |
| **Stop Project** | `make down` |
| **Inside Shell** | `make shell` |
| **Check Logs** | `make logs` |
