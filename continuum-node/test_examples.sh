#!/bin/bash

# Continuum Node - Esempi di Utilizzo Pratici e Test Completi

echo "🚀 Continuum Node - Test e Esempi Completi"
echo "==========================================="

BASE_URL="http://localhost:8080"
DEV_TOKEN="dev-token-strong-and-secret"
GUEST_TOKEN="guest-token-for-testing"

echo ""
echo "1️⃣  HEALTH CHECK"
curl -s "$BASE_URL/health" | jq .

echo ""
echo "2️⃣  LISTA MODELLI (Developer)"
curl -s "$BASE_URL/v1/models" \
  -H "Authorization: Bearer $DEV_TOKEN" | jq .

echo ""
echo "3️⃣  LISTA MODELLI (Guest - limitato)"
curl -s "$BASE_URL/v1/models" \
  -H "Authorization: Bearer $GUEST_TOKEN" | jq .

echo ""
echo "4️⃣  TEST DASHBOARD ACCESS"
echo "Dashboard disponibile a: $BASE_URL/dashboard"
curl -s -I "$BASE_URL/dashboard" | head -5

echo ""
echo "5️⃣  TEST METRICS (Admin)"
curl -s "$BASE_URL/admin/metrics" \
  -H "Authorization: Bearer $DEV_TOKEN" | jq .

echo ""
echo "6️⃣  TEST STATUS (Admin)"
curl -s "$BASE_URL/admin/status" \
  -H "Authorization: Bearer $DEV_TOKEN" | jq .

echo ""
echo "7️⃣  CHAT COMPLETION SEMPLICE"
curl -s "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEV_TOKEN" \
  -d '{
    "model": "llama3:latest",
    "messages": [
      {"role": "user", "content": "Ciao! Come stai?"}
    ]
  }' | jq .

echo ""
echo "8️⃣  CHAT CON IMPOSTAZIONI PERSONALIZZATE"
curl -s "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEV_TOKEN" \
  -d '{
    "model": "llama3:latest",
    "messages": [
      {"role": "system", "content": "Sei un assistente utile e conciso."},
      {"role": "user", "content": "Spiegami la fisica quantistica in 2 frasi."}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }' | jq .

echo ""
echo "6️⃣  STREAMING RESPONSE"
echo "Avviando stream per 10 secondi..."
timeout 10s curl -s "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEV_TOKEN" \
  -d '{
    "model": "llama3:latest",
    "messages": [
      {"role": "user", "content": "Raccontami una breve storia su un robot."}
    ],
    "stream": true
  }' || echo "Stream terminato"

echo ""
echo "🔟  TEST AUTORIZZAZIONE (guest non può usare gpt-4o)"
curl -s "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GUEST_TOKEN" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "Ciao"}
    ]
  }' | jq .

echo ""
echo "1️⃣1️⃣  TEST RATE LIMITING"
echo "Facendo richieste rapide per testare il rate limiting..."
for i in {1..5}; do
    echo "Richiesta $i:"
    curl -s "$BASE_URL/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $GUEST_TOKEN" \
      -d '{
        "model": "llama3:latest",
        "messages": [{"role": "user", "content": "Test"}]
      }' | jq -r '.error.message // "OK"'
    sleep 0.5
done

echo ""
echo "✅ Test completati!"
echo ""
echo "📊 Accedi alla dashboard: $BASE_URL/dashboard"
echo "📈 Metrics API: $BASE_URL/admin/metrics"
echo "🔧 Status API: $BASE_URL/admin/status"
echo "🌐 WebSocket test: $BASE_URL/websocket_test.html"
