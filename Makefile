.PHONY: check setup sync-mcp install-bootstrap install-codex-skill help

# Default target
help:
	@echo "Available commands:"
	@echo "  make check  - Run fast checks (typecheck, lint, tests, build)"
	@echo "  make setup - Initialize project (copy .env.example to .env)"
	@echo "  make sync-mcp - Merge Cursor/Claude MCP servers into OpenAI Chat/Codex config"
	@echo "  make install-bootstrap - Install global solo-new bootstrap command"
	@echo "  make install-codex-skill - Install global Codex bootstrap skill"
	@echo "  make help  - Show this help message"

# Run fast checks
check:
	./scripts/check.sh

# Initialize project environment
setup:
	@echo "Setting up project..."
	@if [ ! -f .env ]; then \
		cp .env.example .env && \
		echo "✓ Created .env from .env.example"; \
	else \
		echo "⚠ .env already exists, skipping"; \
	fi

# Merge MCP server definitions into OpenAI Chat/Codex desktop config
sync-mcp:
	./scripts/sync_mcp_to_openai_chat.sh

# Install global project bootstrap command (~/.local/bin/solo-new)
install-bootstrap:
	./scripts/install_global_bootstrap_command.sh

# Install global Codex skill for natural-language template bootstrap
install-codex-skill:
	./scripts/install_codex_bootstrap_skill.sh
