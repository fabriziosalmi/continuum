#!/bin/bash

# Script di sviluppo per Continuum Node
# Questo script facilita l'avvio del progetto in modalità sviluppo

set -e

echo "🚀 Continuum Node - Modalità Sviluppo"
echo "======================================"

# Controlla se Python è installato
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 non trovato. Installalo prima di continuare."
    exit 1
fi

# Controlla se pip è installato
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 non trovato. Installalo prima di continuare."
    exit 1
fi

# Crea virtual environment se non esiste
if [ ! -d "venv" ]; then
    echo "📦 Creazione virtual environment..."
    python3 -m venv venv
fi

# Attiva virtual environment
echo "🔧 Attivazione virtual environment..."
source venv/bin/activate

# Installa dipendenze
echo "📚 Installazione dipendenze..."
pip install -r requirements.txt

# Controlla se i file di configurazione esistono
if [ ! -f "config/models.yml" ]; then
    echo "❌ File config/models.yml non trovato!"
    exit 1
fi

if [ ! -f "config/users.yml" ]; then
    echo "❌ File config/users.yml non trovato!"
    exit 1
fi

# Imposta variabili d'ambiente per lo sviluppo
export PYTHONPATH="${PWD}"
export HTTP_HOST="${HTTP_HOST:-127.0.0.1}"
export HTTP_PORT="${HTTP_PORT:-8080}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "🌟 Avvio Continuum Node..."
echo "   HTTP Server: http://${HTTP_HOST}:${HTTP_PORT}"
echo "   WebSocket: ws://${HTTP_HOST}:${HTTP_PORT}/v1/chat/completions/ws"
echo ""
echo "📝 Test rapido:"
echo "   curl http://${HTTP_HOST}:${HTTP_PORT}/health"
echo ""
echo "🛑 Premi Ctrl+C per fermare il server"
echo ""

# Avvia l'applicazione
cd app
python main.py
