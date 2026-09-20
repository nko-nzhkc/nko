FROM python:3.13-slim

WORKDIR /app

RUN pip install gunicorn==21.0.1

COPY backend/requirements.txt .

RUN pip install -r requirements.txt --no-cache-dir

COPY backend/ ./

COPY tests/ ./tests/

COPY pytest.ini .

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--access-logfile" , "-", "donor_base.wsgi"]
