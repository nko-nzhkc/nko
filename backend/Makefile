# !make_file

.PHONY: help

help: ## Покажет все доступные команды в make
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## Устанавливает все зависимости проекта из poetry.lock
	poetry install && \

first_run_docker:
	docker compose exec backend poetry run python manage.py collectstatic && \
	docker compose exec backend cp -r /app/static/. /static/static/ && \
	docker compose exec backend poetry run python manage.py makemigrations && \
	docker compose exec backend poetry run python manage.py migrate
