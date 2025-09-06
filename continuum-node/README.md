# Continuum Node

Universal AI Gateway - Un gateway containerizzato che astrae molteplici provider di modelli AI dietro interfacce standardizzate.

## Caratteristiche

- **Bridge HTTP/WebSocket**: API completamente compatibile con OpenAI con supporto WebSocket real-time
- **Protocollo Continuum**: Protocollo TCP nativo ad alte prestazioni (opzionale)
- **Multi-Provider**: Supporta Ollama, OpenAI e facilmente estendibile
- **Autenticazione**: Gestione token-based con autorizzazioni per modello
- **Rate Limiting**: Rate limiting implementato per utente con configurazione flessibile
- **Containerizzato**: Pronto per la produzione con Docker
- **Real-time WebSocket**: Streaming bidirezionale per chat interattive

## Avvio Rapido

1. **Prerequisiti**:
   - Docker e Docker Compose installati
   - Ollama in esecuzione sull'host con il modello `llama3:latest`
   - (Opzionale) Chiave API OpenAI

2. **Configurazione**:
   ```bash
   # Clona o crea la directory del progetto
   cd continuum-node
   
   # (Opzionale) Configura la chiave OpenAI
   export OPENAI_API_KEY="your_openai_api_key_here"
   ```

3. **Avvio**:
   ```bash
   docker-compose up --build
   ```

4. **Test**:
   ```bash
   # Test non-streaming
   curl http://localhost:8080/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer dev-token-strong-and-secret" \
     -d '{
       "model": "llama3:latest",
       "messages": [{"role": "user", "content": "Ciao! Chi sei?"}]
     }'
   
   # Test streaming
   curl http://localhost:8080/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer dev-token-strong-and-secret" \
     -d '{
       "model": "llama3:latest",
       "messages": [{"role": "user", "content": "Raccontami una breve storia."}],
       "stream": true
     }'
   
   # Test WebSocket (usa wscat o simile)
   # wscat -c ws://localhost:8080/v1/chat/completions/ws
   # {"token": "dev-token-strong-and-secret", "model": "llama3:latest", "messages": [{"role": "user", "content": "Ciao!"}]}
   ```

## Configurazione

### Modelli (config/models.yml)

```yaml
models:
  - id: "llama3:latest"
    provider: "ollama"
  - id: "gpt-4o"
    provider: "openai"
```

### Utenti (config/users.yml)

```yaml
users:
  - token: "dev-token-strong-and-secret"
    name: "Developer"
    permissions:
      - "llama3:latest"
      - "gpt-4o"
    rate_limit: "100/minute"
```

## Variabili d'Ambiente

- `OLLAMA_BASE_URL`: URL base per Ollama (default: `http://localhost:11434`)
- `OPENAI_API_KEY`: Chiave API OpenAI
- `HTTP_HOST`: Host del server HTTP (default: `0.0.0.0`)
- `HTTP_PORT`: Porta del server HTTP (default: `8080`)
- `ENABLE_TCP_SERVER`: Abilita il server TCP Continuum (default: `false`)
- `TCP_HOST`: Host del server TCP (default: `0.0.0.0`)
- `TCP_PORT`: Porta del server TCP (default: `8989`)

## API Endpoints

### Health Check
- `GET /health` - Status del servizio

### Modelli
- `GET /v1/models` - Lista modelli disponibili per l'utente

### Chat Completions
- `POST /v1/chat/completions` - Completion di chat (compatibile OpenAI)
- `WS /v1/chat/completions/ws` - WebSocket per chat real-time

### Rate Limiting
Le richieste sono limitate in base alla configurazione utente:
- Formato: `"N/timeunit"` (es. `"100/minute"`, `"10/hour"`)
- Unità supportate: `second`, `minute`, `hour`, `day`
- Risposta 429 quando il limite è superato

## Architettura

```
continuum-node/
├── app/
│   ├── main.py              # Entry point
│   ├── core/                # Protocollo Continuum TCP
│   │   ├── protocol.py      # Serializzazione/deserializzazione
│   │   └── server.py        # Server TCP
│   ├── bridge/              # Bridge HTTP
│   │   ├── http_server.py   # Server FastAPI
│   │   └── models.py        # Modelli Pydantic
│   ├── providers/           # Adattatori AI Provider
│   │   ├── base_provider.py # Interfaccia base
│   │   ├── ollama_provider.py
│   │   └── openai_provider.py
│   └── services/            # Servizi core
│       ├── auth_manager.py  # Autenticazione
│       └── model_router.py  # Routing modelli
├── config/                  # Configurazione
│   ├── models.yml
│   └── users.yml
├── Dockerfile               # Container multi-stage
├── docker-compose.yml       # Orchestrazione
└── requirements.txt         # Dipendenze Python
```

## Sviluppo

Per lo sviluppo locale senza Docker:

```bash
# Opzione 1: Script automatico
./dev.sh

# Opzione 2: Manuale
# Installa le dipendenze
pip install -r requirements.txt

# Avvia il server
cd app
python main.py
```

### WebSocket Client Example

```javascript
// Esempio client WebSocket in JavaScript
const ws = new WebSocket('ws://localhost:8080/v1/chat/completions/ws');

ws.onopen = function() {
    // Invia richiesta di chat
    ws.send(JSON.stringify({
        "token": "dev-token-strong-and-secret",
        "model": "llama3:latest",
        "messages": [{"role": "user", "content": "Ciao!"}],
        "settings": {"temperature": 0.7}
    }));
};

ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    if (response.error) {
        console.error('Error:', response.error);
    } else if (response.choices) {
        const content = response.choices[0].delta.content;
        if (content) {
            console.log('Chunk:', content);
        }
    }
};
```

## Sicurezza

- Utente non-root nel container
- Configurazioni in sola lettura
- Validazione rigorosa degli input
- Rate limiting implementato per utente
- Autenticazione token-based
- WebSocket con autenticazione per messaggio
- Protezione contro overflow del protocollo TCP

## Estensibilità

Per aggiungere un nuovo provider:

1. Creare una classe che eredita da `BaseProvider`
2. Implementare il metodo `stream_completion`
3. Aggiungere il provider al `ModelRouter`
4. Configurare i modelli in `models.yml`
