import os
import json
import aiohttp
from typing import AsyncGenerator, List, Dict, Any
from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    """Provider per l'integrazione con OpenAI."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            # Non lanciare errore qui - sarà gestito nel ModelRouter
            self.api_key = None
        self.base_url = "https://api.openai.com/v1"
        
    async def stream_completion(
        self, messages: List[Dict[str, str]], settings: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Implementa lo streaming delle completion per OpenAI.
        
        Args:
            messages: Lista di messaggi nel formato standard di chat.
            settings: Impostazioni per la generazione (temperature, max_tokens, ecc.).
            
        Yields:
            Chunk di testo della risposta in streaming.
        """
        # Verifica che la chiave API sia disponibile
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        # Estrae il model_id dalle settings
        model_id = settings.get("model", "gpt-4o")
        
        # Prepara il payload per OpenAI
        openai_payload = {
            "model": model_id,
            "messages": messages,
            "stream": True
        }
        
        # Mappa le impostazioni standard ai parametri di OpenAI
        if "temperature" in settings:
            openai_payload["temperature"] = settings["temperature"]
        if "max_tokens" in settings:
            openai_payload["max_tokens"] = settings["max_tokens"]
        if "top_p" in settings:
            openai_payload["top_p"] = settings["top_p"]
        if "frequency_penalty" in settings:
            openai_payload["frequency_penalty"] = settings["frequency_penalty"]
        if "presence_penalty" in settings:
            openai_payload["presence_penalty"] = settings["presence_penalty"]
        
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url,
                    json=openai_payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"OpenAI API error {response.status}: {error_text}")
                    
                    # Legge la risposta Server-Sent Events (SSE)
                    async for line in response.content:
                        if line:
                            try:
                                # Decodifica la linea
                                line_str = line.decode('utf-8').strip()
                                
                                # Ignora le linee vuote e i commenti SSE
                                if not line_str or line_str.startswith(':'):
                                    continue
                                
                                # Processa le linee data: dei Server-Sent Events
                                if line_str.startswith('data: '):
                                    data_content = line_str[6:]  # Rimuove 'data: '
                                    
                                    # Controlla se è il segnale di fine stream
                                    if data_content == '[DONE]':
                                        break
                                    
                                    # Parsa il JSON
                                    chunk_data = json.loads(data_content)
                                    
                                    # Estrae il contenuto dal delta
                                    if "choices" in chunk_data and chunk_data["choices"]:
                                        choice = chunk_data["choices"][0]
                                        if "delta" in choice and "content" in choice["delta"]:
                                            content = choice["delta"]["content"]
                                            if content:
                                                yield content
                                        
                                        # Controlla se è l'ultimo chunk
                                        if choice.get("finish_reason") is not None:
                                            break
                                            
                            except json.JSONDecodeError:
                                # Ignora le linee che non sono JSON validi
                                continue
                            except Exception as e:
                                # Log dell'errore ma continua il processing
                                print(f"Warning: Error processing OpenAI chunk: {e}")
                                continue
                                
            except aiohttp.ClientError as e:
                raise Exception(f"Network error connecting to OpenAI: {e}")
            except Exception as e:
                raise Exception(f"Unexpected error in OpenAI provider: {e}")
