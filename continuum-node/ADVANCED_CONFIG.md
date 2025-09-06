# Esempi di Configurazione Avanzata per Continuum Node

## 1. Configurazione Modelli Estesa (config/models.yml)

```yaml
models:
  # Modelli Ollama
  - id: "llama3:latest"
    provider: "ollama"
    description: "Llama 3 modello generale"
    
  - id: "llama3:8b"
    provider: "ollama"
    description: "Llama 3 8B parametri"
    
  - id: "codellama:latest"
    provider: "ollama"
    description: "Modello specializzato per codice"
  
  # Modelli OpenAI
  - id: "gpt-4o"
    provider: "openai"
    description: "GPT-4 Omni"
    
  - id: "gpt-4o-mini"
    provider: "openai"
    description: "GPT-4 Omni Mini"
    
  - id: "gpt-3.5-turbo"
    provider: "openai"
    description: "GPT-3.5 Turbo"
```

## 2. Configurazione Utenti con Ruoli (config/users.yml)

```yaml
users:
  # Admin - accesso completo
  - token: "admin-super-secret-token-2024"
    name: "Administrator"
    role: "admin"
    permissions:
      - "*"  # Wildcard per tutti i modelli
    rate_limit: "1000/hour"
    
  # Developer - accesso a modelli specifici
  - token: "dev-token-strong-and-secret"
    name: "Developer"
    role: "developer"
    permissions:
      - "llama3:latest"
      - "llama3:8b"
      - "codellama:latest"
      - "gpt-4o-mini"
    rate_limit: "100/minute"
    
  # Guest - accesso limitato
  - token: "guest-token-for-testing"
    name: "Guest User"
    role: "guest"
    permissions:
      - "llama3:latest"
    rate_limit: "10/minute"
    
  # Service account - per API automation
  - token: "service-account-automation-key"
    name: "Automation Service"
    role: "service"
    permissions:
      - "gpt-3.5-turbo"
      - "llama3:8b"
    rate_limit: "500/hour"
```

## 3. Docker Compose per Produzione

```yaml
version: '3.8'
services:
  continuum-node:
    build: .
    container_name: continuum-node-prod
    ports:
      - "8080:8080"
      - "8989:8989"  # Abilita TCP per produzione
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs  # Mount per i log
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - HTTP_HOST=0.0.0.0
      - HTTP_PORT=8080
      - TCP_HOST=0.0.0.0
      - TCP_PORT=8989
      - ENABLE_TCP_SERVER=true
      - LOG_LEVEL=INFO
    networks:
      - ai-network
    restart: unless-stopped
    depends_on:
      - ollama
    
  # Ollama service interno
  ollama:
    image: ollama/ollama:latest
    container_name: ollama-service
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    networks:
      - ai-network
    restart: unless-stopped
    
  # Nginx reverse proxy (opzionale)
  nginx:
    image: nginx:alpine
    container_name: continuum-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - continuum-node
    networks:
      - ai-network
    restart: unless-stopped

volumes:
  ollama_data:

networks:
  ai-network:
    driver: bridge
```

## 4. Configurazione Nginx (nginx.conf)

```nginx
events {
    worker_connections 1024;
}

http {
    upstream continuum_backend {
        server continuum-node:8080;
    }
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    server {
        listen 80;
        server_name localhost;
        
        # Rate limiting
        limit_req zone=api burst=20 nodelay;
        
        # HTTP API
        location /v1/ {
            proxy_pass http://continuum_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # WebSocket
        location /v1/chat/completions/ws {
            proxy_pass http://continuum_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # Health check
        location /health {
            proxy_pass http://continuum_backend;
        }
    }
}
```

## 5. Script di Deploy (deploy.sh)

```bash
#!/bin/bash
set -e

echo "🚀 Deploying Continuum Node to Production"

# Backup configurazione esistente
if [ -d "config_backup" ]; then
    rm -rf config_backup
fi
cp -r config config_backup

# Pull delle immagini più recenti
docker-compose pull

# Build dell'applicazione
docker-compose build --no-cache

# Stop servizi esistenti
docker-compose down

# Avvio in modalità produzione
docker-compose up -d

# Attesa che i servizi siano pronti
echo "⏳ Waiting for services to be ready..."
sleep 30

# Test di connettività
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Continuum Node is running successfully!"
else
    echo "❌ Health check failed!"
    docker-compose logs continuum-node
    exit 1
fi

echo "🎉 Deployment completed successfully!"
```

## 6. Monitoring con Docker Compose

```yaml
# Aggiungere al docker-compose.yml per monitoring
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    networks:
      - ai-network
      
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    networks:
      - ai-network
      
volumes:
  grafana_data:
```
