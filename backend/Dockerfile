FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl

<<<<<<< HEAD
RUN curl -sSL https://install.python-poetry.org | python3 -
=======
COPY backend/requirements.txt .
>>>>>>> main

ENV PATH="/root/.local/bin:$PATH"

<<<<<<< HEAD
COPY pyproject.toml .
=======
COPY backend/ ./

COPY tests/ ./tests/

COPY pytest.ini .
>>>>>>> main

COPY poetry.lock .

RUN poetry install --without dev

COPY backend/ .

CMD ["poetry", "run", "gunicorn", "--bind", "0.0.0.0:8000", "--access-logfile" , "-", "donor_base.wsgi"]
