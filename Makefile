# snap-2-track-backend/Makefile
export PYTHONDONTWRITEBYTECODE=1

VENV = .venv
PYTHON = $(VENV)/bin/python
PORT = 8000

.PHONY: all install clean run dev run-batch

all: install

# -----------------------------------------------------------------------------
# 🐍 Install virtual environment and dependencies
# -----------------------------------------------------------------------------
install:
	@if [ ! -d "$(VENV)" ]; then \
		echo "🐍 Creating virtual environment..."; \
		python3 -m venv $(VENV); \
		echo "🐍 Installing certifi..."; \
		$(VENV)/bin/pip install certifi --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org; \
		echo "🐍 Capturing certifi certificate bundle path and upgrading pip/installing requirements..."; \
		CERT="$$( $(VENV)/bin/python -m certifi )"; \
		echo "Certifi installed at: $$CERT"; \
		echo "🐍 Upgrading pip..."; \
		$(VENV)/bin/pip install --upgrade pip --cert=$$CERT --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org; \
		echo "🐍 Installing remaining requirements..."; \
		$(VENV)/bin/pip install -r requirements.txt --cert=$$CERT --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org; \
		echo "✅ Installation complete."; \
	else \
		echo "✅ Virtual environment already exists. Skipping installation."; \
	fi

# -----------------------------------------------------------------------------
# 🚀 Run commands
# -----------------------------------------------------------------------------
run:
	@echo "🚀 Starting Backend (Production)..."
	@$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

dev:
	@echo "🛠️  Starting Backend (Dev/Reload)..."
	@$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

run-batch:
	@echo "📸 Processing images in ./pictures..."
	@$(PYTHON) process_local_images.py

generate-key:
	@echo "Generating key"
	@$(PYTHON) generate_key.py


# -----------------------------------------------------------------------------
# 🧹 Cleanup
# -----------------------------------------------------------------------------
clean:
	@echo "🧹 Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@rm -rf $(VENV)

