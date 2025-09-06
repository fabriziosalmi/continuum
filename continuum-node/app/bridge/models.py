from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union


class ChatMessage(BaseModel):
    """Rappresenta un messaggio di chat."""
    role: str = Field(..., description="Il ruolo del messaggio (user, assistant, system)")
    content: str = Field(..., description="Il contenuto del messaggio")


class ChatCompletionRequest(BaseModel):
    """Richiesta per la completion di chat compatibile con OpenAI."""
    model: str = Field(..., description="ID del modello da utilizzare")
    messages: List[ChatMessage] = Field(..., description="Lista dei messaggi di conversazione")
    stream: Optional[bool] = Field(False, description="Se restituire la risposta in streaming")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Controllo della casualità")
    max_tokens: Optional[int] = Field(None, gt=0, description="Numero massimo di token da generare")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nucleus sampling")
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Penalità per la frequenza")
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Penalità per la presenza")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Sequenze di stop")


class ChatCompletionChoice(BaseModel):
    """Rappresenta una scelta nella risposta di completion."""
    index: int = Field(..., description="Indice della scelta")
    message: ChatMessage = Field(..., description="Il messaggio generato")
    finish_reason: Optional[str] = Field(None, description="Motivo della fine della generazione")


class ChatCompletionUsage(BaseModel):
    """Rappresenta l'utilizzo di token nella risposta."""
    prompt_tokens: int = Field(..., description="Numero di token nel prompt")
    completion_tokens: int = Field(..., description="Numero di token nella completion")
    total_tokens: int = Field(..., description="Numero totale di token utilizzati")


class ChatCompletionResponse(BaseModel):
    """Risposta completa per la completion di chat compatibile con OpenAI."""
    id: str = Field(..., description="ID univoco della completion")
    object: str = Field("chat.completion", description="Tipo di oggetto")
    created: int = Field(..., description="Timestamp Unix di creazione")
    model: str = Field(..., description="Modello utilizzato")
    choices: List[ChatCompletionChoice] = Field(..., description="Lista delle scelte generate")
    usage: Optional[ChatCompletionUsage] = Field(None, description="Informazioni sull'utilizzo")


class ChatCompletionStreamChoice(BaseModel):
    """Rappresenta una scelta nel chunk di streaming."""
    index: int = Field(..., description="Indice della scelta")
    delta: Dict[str, Any] = Field(..., description="Delta del messaggio")
    finish_reason: Optional[str] = Field(None, description="Motivo della fine della generazione")


class ChatCompletionStreamResponse(BaseModel):
    """Risposta di streaming per la completion di chat compatibile con OpenAI."""
    id: str = Field(..., description="ID univoco della completion")
    object: str = Field("chat.completion.chunk", description="Tipo di oggetto")
    created: int = Field(..., description="Timestamp Unix di creazione")
    model: str = Field(..., description="Modello utilizzato")
    choices: List[ChatCompletionStreamChoice] = Field(..., description="Lista delle scelte in streaming")


class ErrorResponse(BaseModel):
    """Risposta di errore standardizzata."""
    error: Dict[str, Any] = Field(..., description="Dettagli dell'errore")
    
    
class ErrorDetail(BaseModel):
    """Dettagli dell'errore."""
    message: str = Field(..., description="Messaggio di errore")
    type: str = Field(..., description="Tipo di errore")
    code: Optional[str] = Field(None, description="Codice di errore")
