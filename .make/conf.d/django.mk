# Make targets for Django projects

# Migrate all database changes
.PHONY: migrate
migrate:
	@echo "Migrating the database"
	@python ../demolizzen/manage.py migrate $(package)

# Make migrations for the app
.PHONY: migrations
migrations:
	@echo "Creating or updating migrations"
	@python ../demolizzen/manage.py makemigrations $(package)

# Help message
.PHONY: help
help::
	@echo "  $(TEXT_UNDERLINE)Django:$(TEXT_UNDERLINE_END)"
	@echo "    Migration handling:"
	@echo "      migrate                   Migrate all database changes"
	@echo "      migrations                Create or update migrations"
	@echo ""
