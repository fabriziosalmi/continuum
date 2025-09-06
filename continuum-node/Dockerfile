# Stage 1: Builder
FROM python:3.11-slim as builder

# Installa le dipendenze di sistema necessarie per la compilazione
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Crea e attiva un ambiente virtuale
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copia e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Final
FROM python:3.11-slim as final

# Crea un utente non-root per la sicurezza
RUN groupadd -r continuum && useradd -r -g continuum continuum

# Copia l'ambiente virtuale dal builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Crea le directory necessarie
RUN mkdir -p /app /app/config && \
    chown -R continuum:continuum /app

# Imposta la directory di lavoro
WORKDIR /app

# Copia il codice dell'applicazione
COPY app/ ./app/
COPY config/ ./config/

# Imposta i permessi
RUN chown -R continuum:continuum /app

# Cambia all'utente non-root
USER continuum

# Variabili d'ambiente
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8080
ENV TCP_HOST=0.0.0.0
ENV TCP_PORT=8989
ENV ENABLE_TCP_SERVER=false

# Espone le porte
EXPOSE 8080 8989

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Comando di avvio
CMD ["python", "-m", "app.main"]
