#!/usr/bin/env python3
"""
Continuum Node - Client Python di Esempio
Mostra come utilizzare Continuum Node da Python
"""

import requests
import json
import websocket
import threading
import time

class ContinuumClient:
    def __init__(self, base_url="http://localhost:8080", token="dev-token-strong-and-secret"):
        self.base_url = base_url
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def health_check(self):
        """Controlla lo stato del servizio"""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def list_models(self):
        """Ottiene la lista dei modelli disponibili"""
        response = requests.get(f"{self.base_url}/v1/models", headers=self.headers)
        return response.json()
    
    def chat_completion(self, model, messages, stream=False, **kwargs):
        """Effettua una chat completion"""
        data = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers=self.headers,
            json=data,
            stream=stream
        )
        
        if stream:
            return self._handle_stream(response)
        else:
            return response.json()
    
    def _handle_stream(self, response):
        """Gestisce le risposte in streaming"""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Rimuove 'data: '
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        yield data
                    except json.JSONDecodeError:
                        continue

class ContinuumWebSocketClient:
    def __init__(self, token="dev-token-strong-and-secret"):
        self.token = token
        self.ws = None
        self.connected = False
        
    def connect(self):
        """Connette al WebSocket"""
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self.on_message_received(data)
            except json.JSONDecodeError:
                print(f"Errore parsing: {message}")
        
        def on_error(ws, error):
            print(f"Errore WebSocket: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            self.connected = False
            print("Connessione WebSocket chiusa")
        
        def on_open(ws):
            self.connected = True
            print("Connessione WebSocket stabilita")
        
        self.ws = websocket.WebSocketApp(
            "ws://localhost:8080/v1/chat/completions/ws",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # Avvia in thread separato
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
        
        # Attendi connessione
        timeout = 5
        while not self.connected and timeout > 0:
            time.sleep(0.1)
            timeout -= 0.1
        
        return self.connected
    
    def send_message(self, model, messages, **settings):
        """Invia un messaggio via WebSocket"""
        if not self.connected:
            raise Exception("Non connesso al WebSocket")
        
        data = {
            "token": self.token,
            "model": model,
            "messages": messages,
            "settings": settings
        }
        
        self.ws.send(json.dumps(data))
    
    def on_message_received(self, data):
        """Override questo metodo per gestire i messaggi ricevuti"""
        if "error" in data:
            print(f"Errore: {data['error']['message']}")
        elif "choices" in data:
            content = data["choices"][0]["delta"].get("content", "")
            if content:
                print(content, end="", flush=True)
            if data["choices"][0].get("finish_reason"):
                print("\n--- Fine risposta ---")
    
    def disconnect(self):
        """Disconnette dal WebSocket"""
        if self.ws:
            self.ws.close()

def main():
    """Esempi di utilizzo"""
    print("🚀 Continuum Node - Client Python")
    print("=" * 40)
    
    # Client REST
    client = ContinuumClient()
    
    print("\n1️⃣  Health Check")
    health = client.health_check()
    print(f"Status: {health}")
    
    print("\n2️⃣  Lista Modelli")
    models = client.list_models()
    print(f"Modelli disponibili: {[m['id'] for m in models['data']]}")
    
    print("\n3️⃣  Chat Completion (Non-streaming)")
    try:
        response = client.chat_completion(
            model="llama3:latest",
            messages=[
                {"role": "user", "content": "Ciao! Dimmi una cosa interessante in una frase."}
            ]
        )
        if "choices" in response:
            print(f"Risposta: {response['choices'][0]['message']['content']}")
        else:
            print(f"Errore: {response}")
    except Exception as e:
        print(f"Errore: {e}")
    
    print("\n4️⃣  Chat Completion (Streaming)")
    try:
        print("Risposta in streaming:")
        for chunk in client.chat_completion(
            model="llama3:latest",
            messages=[
                {"role": "user", "content": "Conta da 1 a 5"}
            ],
            stream=True
        ):
            if "choices" in chunk:
                content = chunk["choices"][0]["delta"].get("content", "")
                if content:
                    print(content, end="", flush=True)
        print("\n--- Fine streaming ---")
    except Exception as e:
        print(f"Errore streaming: {e}")
    
    print("\n5️⃣  WebSocket Test")
    try:
        ws_client = ContinuumWebSocketClient()
        if ws_client.connect():
            print("Invio messaggio via WebSocket...")
            ws_client.send_message(
                model="llama3:latest",
                messages=[
                    {"role": "user", "content": "Ciao via WebSocket! Rispondi brevemente."}
                ],
                temperature=0.7
            )
            # Attendi risposta
            time.sleep(5)
            ws_client.disconnect()
        else:
            print("Impossibile connettersi al WebSocket")
    except Exception as e:
        print(f"Errore WebSocket: {e}")

if __name__ == "__main__":
    main()
