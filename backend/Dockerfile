FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml .

COPY poetry.lock .

RUN poetry install --without dev

COPY . .

CMD ["poetry", "run", "gunicorn", "--bind", "0.0.0.0:8000", "--access-logfile" , "-", "donor_base.wsgi"]
