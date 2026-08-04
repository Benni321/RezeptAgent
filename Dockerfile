# RezeptAgent - gemeinsames Image fuer API und GUI (W7)
FROM python:3.11-slim

WORKDIR /app

# Abhaengigkeiten zuerst (besseres Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode
COPY . .

# Standard: API starten (die GUI ueberschreibt das Command in docker-compose).
# Beide Ports dokumentieren: 8000 = FastAPI, 8501 = Streamlit-GUI.
EXPOSE 8000 8501
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
