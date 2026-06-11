# Start all services
up:
	sudo docker compose up -d

# Stop all services
down:
	sudo docker compose down

# Rebuild and start
build:
	sudo docker compose up -d --build

# Run author normalization query
query:
	sudo docker compose exec app python app/query.py

# Run any script (usage: make run file=app/some_script.py)
run:
	sudo docker compose exec app python $(file)

# Open shell in app container
shell:
	sudo docker compose exec app bash

# View logs
logs:
	sudo docker compose logs -f app

# Clean optimized data (removes the built image to force regeneration)
clean:
	sudo docker compose down --rmi all
	rm -f symspell_index.pickle ps_supplier/ps_supplier.pkl
