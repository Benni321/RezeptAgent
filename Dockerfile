# RezeptAgent - gemeinsames Image fuer API und GUI (W7)
FROM python:3.11-slim

WORKDIR /app

# Abhaengigkeiten zuerst (besseres Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode
COPY . .

# Standard: API starten (die GUI ueberschreibt das Command in docker-compose)
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
