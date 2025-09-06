import json
import struct
import asyncio
from typing import Tuple, Dict, Any


class ContinuumProtocol:
    """Implementa la serializzazione/deserializzazione per il Continuum Protocol."""
    
    @staticmethod
    def pack_message(msg_type: str, payload: Dict[str, Any]) -> bytes:
        """
        Serializza un messaggio nel formato wire del Continuum Protocol.
        
        Wire Format: [TYPE: 4 bytes ASCII][LENGTH: 4 bytes unsigned int big-endian][PAYLOAD: JSON in UTF-8]
        
        Args:
            msg_type: Tipo di messaggio (max 4 caratteri ASCII)
            payload: Dizionario da serializzare come JSON
            
        Returns:
            Messaggio serializzato in bytes
        """
        if len(msg_type) > 4:
            raise ValueError(f"Message type '{msg_type}' exceeds 4 characters")
        
        # Padda il tipo a 4 caratteri con spazi
        padded_type = msg_type.ljust(4)[:4]
        
        # Serializza il payload in JSON UTF-8
        payload_json = json.dumps(payload, ensure_ascii=False)
        payload_bytes = payload_json.encode('utf-8')
        payload_length = len(payload_bytes)
        
        # Crea il messaggio: TYPE (4 bytes) + LENGTH (4 bytes big-endian) + PAYLOAD
        message = (
            padded_type.encode('ascii') +
            struct.pack('>I', payload_length) +
            payload_bytes
        )
        
        return message
    
    @staticmethod
    async def unpack_message_from_stream(reader: asyncio.StreamReader) -> Tuple[str, Dict[str, Any]]:
        """
        Deserializza un messaggio dal stream nel formato Continuum Protocol.
        
        Args:
            reader: Stream reader asincrono
            
        Returns:
            Tupla contenente (tipo_messaggio, payload_dizionario)
            
        Raises:
            ConnectionError: Se la connessione si chiude inaspettatamente
            ValueError: Se il formato del messaggio non è valido
        """
        # Legge il tipo di messaggio (4 bytes ASCII)
        type_bytes = await reader.readexactly(4)
        if len(type_bytes) != 4:
            raise ConnectionError("Connection closed while reading message type")
        
        msg_type = type_bytes.decode('ascii').rstrip()
        
        # Legge la lunghezza del payload (4 bytes unsigned int big-endian)
        length_bytes = await reader.readexactly(4)
        if len(length_bytes) != 4:
            raise ConnectionError("Connection closed while reading message length")
        
        payload_length = struct.unpack('>I', length_bytes)[0]
        
        # Valida la lunghezza del payload (protezione contro messaggi troppo grandi)
        if payload_length > 10 * 1024 * 1024:  # 10 MB max
            raise ValueError(f"Payload too large: {payload_length} bytes")
        
        # Legge il payload
        if payload_length > 0:
            payload_bytes = await reader.readexactly(payload_length)
            if len(payload_bytes) != payload_length:
                raise ConnectionError("Connection closed while reading payload")
            
            # Deserializza il JSON
            try:
                payload_json = payload_bytes.decode('utf-8')
                payload = json.loads(payload_json)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise ValueError(f"Invalid payload format: {e}")
        else:
            payload = {}
        
        return msg_type, payload
    
    @staticmethod
    def create_auth_request(token: str) -> bytes:
        """
        Crea un messaggio di richiesta di autenticazione.
        
        Args:
            token: Token di autenticazione
            
        Returns:
            Messaggio di autenticazione serializzato
        """
        return ContinuumProtocol.pack_message("AUTH", {"token": token})
    
    @staticmethod
    def create_auth_response(success: bool, message: str = "", user_info: Dict[str, Any] = None) -> bytes:
        """
        Crea un messaggio di risposta di autenticazione.
        
        Args:
            success: Se l'autenticazione è riuscita
            message: Messaggio di stato
            user_info: Informazioni dell'utente se autenticato
            
        Returns:
            Messaggio di risposta serializzato
        """
        payload = {
            "success": success,
            "message": message
        }
        if user_info:
            payload["user"] = user_info
            
        return ContinuumProtocol.pack_message("ARSP", payload)
    
    @staticmethod
    def create_completion_request(
        model: str, 
        messages: list, 
        settings: Dict[str, Any] = None
    ) -> bytes:
        """
        Crea un messaggio di richiesta di completion.
        
        Args:
            model: ID del modello
            messages: Lista dei messaggi
            settings: Impostazioni aggiuntive
            
        Returns:
            Messaggio di richiesta serializzato
        """
        payload = {
            "model": model,
            "messages": messages
        }
        if settings:
            payload["settings"] = settings
            
        return ContinuumProtocol.pack_message("COMP", payload)
    
    @staticmethod
    def create_completion_chunk(content: str, is_final: bool = False) -> bytes:
        """
        Crea un messaggio di chunk di completion.
        
        Args:
            content: Contenuto del chunk
            is_final: Se questo è l'ultimo chunk
            
        Returns:
            Messaggio di chunk serializzato
        """
        payload = {
            "content": content,
            "final": is_final
        }
        return ContinuumProtocol.pack_message("CHNK", payload)
    
    @staticmethod
    def create_error_response(error_code: str, error_message: str) -> bytes:
        """
        Crea un messaggio di errore.
        
        Args:
            error_code: Codice di errore
            error_message: Messaggio di errore
            
        Returns:
            Messaggio di errore serializzato
        """
        payload = {
            "code": error_code,
            "message": error_message
        }
        return ContinuumProtocol.pack_message("ERRO", payload)
