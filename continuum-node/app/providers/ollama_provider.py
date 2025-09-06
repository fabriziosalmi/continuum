import os
import json
import aiohttp
from typing import AsyncGenerator, List, Dict, Any
from .base_provider import BaseProvider


class OllamaProvider(BaseProvider):
    """Provider per l'integrazione con Ollama."""

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async def stream_completion(
        self, messages: List[Dict[str, str]], settings: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Implementa lo streaming delle completion per Ollama.

        Args:
            messages: Lista di messaggi nel formato standard di chat.
            settings: Impostazioni per la generazione (temperature, max_tokens, ecc.).

        Yields:
            Chunk di testo della risposta in streaming.
        """
        # Estrae il model_id dalle settings
        model_id = settings.get("model", "llama3:latest")

        # Prepara il payload per Ollama
        ollama_payload = {
            "model": model_id,
            "messages": messages,
            "stream": True,
            "options": {},
        }

        # Mappa le impostazioni standard ai parametri di Ollama
        if "temperature" in settings:
            ollama_payload["options"]["temperature"] = settings["temperature"]
        if "max_tokens" in settings:
            ollama_payload["options"]["num_predict"] = settings["max_tokens"]
        if "top_p" in settings:
            ollama_payload["options"]["top_p"] = settings["top_p"]

        url = f"{self.base_url}/api/chat"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url,
                    json=ollama_payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"Ollama API error {response.status}: {error_text}"
                        )

                    # Legge la risposta in streaming
                    async for line in response.content:
                        if line:
                            try:
                                # Decodifica la linea JSON
                                line_str = line.decode("utf-8").strip()
                                if line_str:
                                    chunk_data = json.loads(line_str)

                                    # Estrae il contenuto del messaggio se presente
                                    if (
                                        "message" in chunk_data
                                        and "content" in chunk_data["message"]
                                    ):
                                        content = chunk_data["message"]["content"]
                                        if content:
                                            yield content

                                    # Controlla se è l'ultimo chunk
                                    if chunk_data.get("done", False):
                                        break

                            except json.JSONDecodeError:
                                # Ignora le linee che non sono JSON validi
                                continue
                            except Exception as e:
                                # Log dell'errore ma continua il processing
                                print(f"Warning: Error processing Ollama chunk: {e}")
                                continue

            except aiohttp.ClientError as e:
                raise Exception(f"Network error connecting to Ollama: {e}")
            except Exception as e:
                raise Exception(f"Unexpected error in Ollama provider: {e}")
