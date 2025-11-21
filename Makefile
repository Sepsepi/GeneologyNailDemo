.PHONY: help setup start stop restart logs clean load-data test db-shell api-docs

help:
	@echo "Genealogy Data Pipeline - Quick Commands"
	@echo ""
	@echo "Setup & Run:"
	@echo "  make setup       - Initial setup (copy .env, build containers)"
	@echo "  make start       - Start all services"
	@echo "  make stop        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo ""
	@echo "Data & Testing:"
	@echo "  make load-data   - Load sample genealogy data"
	@echo "  make test        - Run test suite"
	@echo "  make clean       - Clean up containers and volumes"
	@echo ""
	@echo "Utilities:"
	@echo "  make logs        - View service logs"
	@echo "  make db-shell    - Connect to PostgreSQL"
	@echo "  make api-docs    - Open API documentation"
	@echo ""

setup:
	@echo "Setting up Genealogy Data Pipeline..."
	@cp -n .env.example .env || true
	@docker-compose build
	@echo "✓ Setup complete! Run 'make start' to begin."

start:
	@echo "Starting all services..."
	@docker-compose up -d
	@echo "✓ Services started!"
	@echo "  API: http://localhost:8000"
	@echo "  Docs: http://localhost:8000/docs"
	@echo ""
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "✓ Ready! Run 'make load-data' to import sample records."

stop:
	@echo "Stopping all services..."
	@docker-compose down
	@echo "✓ Services stopped."

restart:
	@echo "Restarting services..."
	@docker-compose restart
	@echo "✓ Services restarted."

logs:
	@docker-compose logs -f

clean:
	@echo "Cleaning up containers and volumes..."
	@docker-compose down -v
	@echo "✓ Cleanup complete."

load-data:
	@echo "Loading sample genealogy data..."
	@pip install -q requests 2>/dev/null || true
	@python scripts/load_sample_data.py
	@echo ""
	@echo "✓ Sample data loaded successfully!"
	@echo ""
	@echo "Try these commands:"
	@echo "  curl http://localhost:8000/api/leads?min_score=50 | jq"
	@echo "  curl http://localhost:8000/api/leads/1 | jq"

test:
	@echo "Running test suite..."
	@pytest -v tests/
	@echo "✓ Tests complete."

test-coverage:
	@echo "Running tests with coverage..."
	@pytest --cov=app tests/
	@echo "✓ Coverage report generated."

db-shell:
	@echo "Connecting to PostgreSQL..."
	@docker-compose exec db psql -U genealogy_user -d genealogy_db

api-docs:
	@echo "Opening API documentation..."
	@open http://localhost:8000/docs || xdg-open http://localhost:8000/docs || echo "Visit http://localhost:8000/docs"

quick-test: start load-data
	@echo ""
	@echo "=== Quick Test Complete ==="
	@echo ""
	@echo "Fetching sample leads..."
	@curl -s http://localhost:8000/api/leads?min_score=50 | jq '.[] | {name: .name, score: .lead_score, ancestor: .german_ancestor.name}'
	@echo ""
	@echo "✓ System is working! Visit http://localhost:8000/docs for full API."

install-dev:
	@echo "Installing development dependencies..."
	@pip install -r requirements.txt
	@pip install pytest pytest-cov black flake8
	@echo "✓ Development environment ready."

format:
	@echo "Formatting code with black..."
	@black app/ tests/
	@echo "✓ Code formatted."

lint:
	@echo "Linting code..."
	@flake8 app/ tests/ --max-line-length=120
	@echo "✓ Linting complete."
