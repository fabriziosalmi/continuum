import time
import uuid
import json
from fastapi import FastAPI, HTTPException, Header, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, AsyncGenerator
import os
from pathlib import Path
from ..services.auth_manager import AuthManager
from ..services.model_router import ModelRouter
from ..services.enhanced_logging import enhanced_logger
import time
from fastapi import Request
from .models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    ChatCompletionStreamResponse,
    ChatCompletionStreamChoice,
    ErrorResponse,
    ErrorDetail
)


class HTTPServer:
    """Server HTTP FastAPI per il bridge compatibile con OpenAI."""
    
    def __init__(self, auth_manager: AuthManager, model_router: ModelRouter) -> None:
        self.auth_manager = auth_manager
        self.model_router = model_router
        self._start_time = time.time()
        self._request_count = 0
        self._active_websockets = []
        
        self.app = FastAPI(
            title="Continuum Node",
            description="Universal AI Gateway - OpenAI Compatible API",
            version="1.0.0"
        )
        
        # Configura CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Middleware per tracking richieste
        @self.app.middleware("http")
        async def track_requests(request: Request, call_next):
            start_time = time.time()
            
            # Estrai token se presente
            auth_header = request.headers.get("authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
            
            response = await call_next(request)
            
            # Log della richiesta
            process_time = time.time() - start_time
            enhanced_logger.log_request(
                endpoint=str(request.url.path),
                method=request.method,
                status_code=response.status_code,
                response_time=process_time,
                user_token=token
            )
            
            # Aggiorna contatore
            self._request_count += 1
            
            return response
        
        # Registra le rotte
        self._register_routes()
        self._setup_static_files()
    
    def _setup_static_files(self) -> None:
        """Configura i file statici per la dashboard."""
        # Trova la directory root del progetto
        current_dir = Path(__file__).parent.parent.parent
        
        # Endpoint per la dashboard
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """Serve la dashboard principale."""
            dashboard_path = current_dir / "dashboard.html"
            if dashboard_path.exists():
                return FileResponse(dashboard_path)
            else:
                return HTMLResponse("""
                <html>
                    <body>
                        <h1>Continuum Node API</h1>
                        <p>Dashboard non trovata. API endpoints disponibili:</p>
                        <ul>
                            <li><a href="/health">Health Check</a></li>
                            <li><a href="/docs">API Documentation</a></li>
                            <li><a href="/v1/models">Models (richiede auth)</a></li>
                        </ul>
                    </body>
                </html>
                """)
        
        # Endpoint per file statici della dashboard
        @self.app.get("/dashboard")
        async def get_dashboard():
            """Serve la dashboard."""
            return await dashboard()
        
        # Endpoint per metrics e monitoring
        @self.app.get("/metrics")
        async def metrics():
            """Endpoint per metriche del sistema."""
            return enhanced_logger.get_metrics_summary()
        
        @self.app.get("/metrics/detailed")
        async def detailed_metrics(limit: int = 100):
            """Endpoint per metriche dettagliate."""
            return {
                "metrics": enhanced_logger.get_detailed_metrics(limit),
                "summary": enhanced_logger.get_metrics_summary()
            }
        
        @self.app.get("/admin/status")
        async def admin_status(token: str = Depends(self._extract_token)):
            """Status completo del sistema (solo admin)."""
            user = self.auth_manager.authenticate(token)
            if not user or user.name != "Administrator":
                raise HTTPException(status_code=403, detail="Admin access required")
            
            return {
                "system": {
                    "uptime": time.time() - self._start_time,
                    "total_requests": self._request_count,
                    "active_websockets": len(self._active_websockets),
                    "memory_usage": self._get_memory_usage()
                },
                "models": {
                    "available": len(self.model_router.get_available_models()),
                    "list": [{"id": m, "provider": self.model_router.get_model_config(m)} 
                           for m in self.model_router.get_available_models()]
                },
                "users": {
                    "total": len(self.auth_manager.users),
                    "rate_limits": {token: len(limits) for token, limits in self.auth_manager.rate_limit_tracker.items()}
                },
                "metrics": enhanced_logger.get_metrics_summary()
            }
        
        def _get_memory_usage(self):
            """Ottiene info sulla memoria (se disponibile)."""
            try:
                import psutil
                process = psutil.Process()
                return {
                    "rss_mb": process.memory_info().rss / 1024 / 1024,
                    "cpu_percent": process.cpu_percent()
                }
            except ImportError:
                return {"error": "psutil not available"}
    
    def _get_memory_usage(self):
        """Ottiene info sulla memoria (se disponibile)."""
        try:
            import psutil
            process = psutil.Process()
            return {
                "rss_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_percent": process.cpu_percent()
            }
        except ImportError:
            return {"error": "psutil not available"}
    
    def _register_routes(self) -> None:
        """Registra tutte le rotte dell'API."""
        
        @self.app.get("/health")
        async def health_check():
            """Endpoint di health check."""
            return {"status": "healthy", "timestamp": int(time.time())}
        
        @self.app.get("/v1/models")
        async def list_models(token: str = Depends(self._extract_token)):
            """Lista i modelli disponibili."""
            # Verifica autenticazione
            user = self.auth_manager.authenticate(token)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid authentication token")
            
            # Restituisce solo i modelli per cui l'utente ha i permessi
            available_models = []
            for model_id in self.model_router.get_available_models():
                if self.auth_manager.is_authorized(token, model_id):
                    available_models.append({
                        "id": model_id,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "continuum-node"
                    })
            
            return {"object": "list", "data": available_models}
        
        @self.app.post("/v1/chat/completions")
        async def chat_completions(
            request: ChatCompletionRequest,
            token: str = Depends(self._extract_token)
        ):
            """Endpoint principale per le completion di chat."""
            
            # Verifica autenticazione
            user = self.auth_manager.authenticate(token)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid authentication token")
            
            # Verifica rate limiting
            if not self.auth_manager.check_rate_limit(token):
                raise HTTPException(
                    status_code=429, 
                    detail="Rate limit exceeded. Please try again later."
                )
            
            # Verifica autorizzazione per il modello
            if not self.auth_manager.is_authorized(token, request.model):
                raise HTTPException(
                    status_code=403, 
                    detail=f"User not authorized to use model: {request.model}"
                )
            
            # Verifica che il modello sia disponibile
            provider = self.model_router.get_provider_for_model(request.model)
            if not provider:
                raise HTTPException(
                    status_code=404,
                    detail=f"Model not found: {request.model}"
                )
            
            # Prepara le impostazioni per il provider
            settings = {
                "model": request.model,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "top_p": request.top_p,
                "frequency_penalty": request.frequency_penalty,
                "presence_penalty": request.presence_penalty,
                "stop": request.stop
            }
            
            # Rimuove i valori None
            settings = {k: v for k, v in settings.items() if v is not None}
            
            # Converte i messaggi nel formato standard
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            try:
                if request.stream:
                    # Risposta in streaming
                    return StreamingResponse(
                        self._stream_chat_completion(provider, messages, settings, request.model),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Access-Control-Allow-Origin": "*"
                        }
                    )
                else:
                    # Risposta non in streaming
                    return await self._complete_chat_completion(provider, messages, settings, request.model)
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error generating completion: {str(e)}")
        
        @self.app.websocket("/v1/chat/completions/ws")
        async def websocket_chat_completions(websocket: WebSocket):
            """Endpoint WebSocket per completion di chat in tempo reale."""
            await websocket.accept()
            self._active_websockets.append(websocket)
            
            client_ip = websocket.client.host if websocket.client else "unknown"
            enhanced_logger.log_websocket_event("connection_opened", "unknown", client_ip=client_ip)
            
            try:
                while True:
                    # Riceve il messaggio dal client
                    data = await websocket.receive_json()
                    
                    # Estrae il token
                    token = data.get("token")
                    if not token:
                        await websocket.send_json({
                            "error": {"message": "Missing token", "type": "authentication_error"}
                        })
                        enhanced_logger.log_websocket_event("auth_failed", "no_token", reason="missing_token")
                        continue
                    
                    # Verifica autenticazione
                    user = self.auth_manager.authenticate(token)
                    if not user:
                        await websocket.send_json({
                            "error": {"message": "Invalid token", "type": "authentication_error"}
                        })
                        enhanced_logger.log_websocket_event("auth_failed", token, reason="invalid_token")
                        continue
                    
                    # Verifica rate limiting
                    if not self.auth_manager.check_rate_limit(token):
                        await websocket.send_json({
                            "error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}
                        })
                        enhanced_logger.log_websocket_event("rate_limit_exceeded", token, user=user.name)
                        continue
                    
                    # Estrae la richiesta
                    model = data.get("model")
                    messages = data.get("messages", [])
                    settings = data.get("settings", {})
                    
                    if not model:
                        await websocket.send_json({
                            "error": {"message": "Missing model", "type": "validation_error"}
                        })
                        continue
                    
                    # Verifica autorizzazione
                    if not self.auth_manager.is_authorized(token, model):
                        await websocket.send_json({
                            "error": {"message": f"Not authorized for model: {model}", "type": "authorization_error"}
                        })
                        enhanced_logger.log_websocket_event("unauthorized_model", token, model=model, user=user.name)
                        continue
                    
                    # Ottiene il provider
                    provider = self.model_router.get_provider_for_model(model)
                    if not provider:
                        await websocket.send_json({
                            "error": {"message": f"Model not found: {model}", "type": "model_error"}
                        })
                        continue
                    
                    # Log inizio completion
                    enhanced_logger.log_model_operation("completion_start", model, token, 
                                                       user=user.name, message_count=len(messages))
                    
                    # Prepara le settings
                    settings["model"] = model
                    
                    try:
                        # Invia la risposta in streaming via WebSocket
                        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
                        start_time = time.time()
                        
                        async for chunk in provider.stream_completion(messages, settings):
                            if chunk:
                                response = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": chunk},
                                        "finish_reason": None
                                    }]
                                }
                                await websocket.send_json(response)
                        
                        # Invia il chunk finale
                        final_response = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop"
                            }]
                        }
                        await websocket.send_json(final_response)
                        
                        # Log completamento
                        completion_time = time.time() - start_time
                        enhanced_logger.log_model_operation("completion_success", model, token,
                                                           user=user.name, duration=completion_time)
                        
                    except Exception as e:
                        await websocket.send_json({
                            "error": {"message": f"Generation error: {str(e)}", "type": "generation_error"}
                        })
                        enhanced_logger.log_model_operation("completion_error", model, token,
                                                           user=user.name, error=str(e))
                        
            except WebSocketDisconnect:
                enhanced_logger.log_websocket_event("connection_closed", "unknown", reason="client_disconnect")
            except Exception as e:
                enhanced_logger.log_websocket_event("connection_error", "unknown", error=str(e))
                try:
                    await websocket.send_json({
                        "error": {"message": f"Server error: {str(e)}", "type": "server_error"}
                    })
                except:
                    pass
            finally:
                if websocket in self._active_websockets:
                    self._active_websockets.remove(websocket)
    
    async def _extract_token(self, authorization: Optional[str] = Header(None)) -> str:
        """Estrae il token di autorizzazione dall'header."""
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header missing")
        
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        return authorization[7:]  # Rimuove "Bearer "
    
    async def _stream_chat_completion(
        self, 
        provider, 
        messages: list, 
        settings: dict, 
        model: str
    ) -> AsyncGenerator[str, None]:
        """Genera una risposta in streaming nel formato SSE."""
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        
        try:
            async for chunk in provider.stream_completion(messages, settings):
                if chunk:
                    # Crea il chunk di risposta
                    stream_response = ChatCompletionStreamResponse(
                        id=completion_id,
                        created=created,
                        model=model,
                        choices=[
                            ChatCompletionStreamChoice(
                                index=0,
                                delta={"content": chunk},
                                finish_reason=None
                            )
                        ]
                    )
                    
                    # Invia il chunk nel formato SSE
                    yield f"data: {stream_response.model_dump_json()}\n\n"
            
            # Invia il chunk finale
            final_response = ChatCompletionStreamResponse(
                id=completion_id,
                created=created,
                model=model,
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta={},
                        finish_reason="stop"
                    )
                ]
            )
            yield f"data: {final_response.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            # Invia un messaggio di errore in streaming
            error_response = {
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": "stream_error"
                }
            }
            yield f"data: {json.dumps(error_response)}\n\n"
    
    async def _complete_chat_completion(
        self, 
        provider, 
        messages: list, 
        settings: dict, 
        model: str
    ) -> ChatCompletionResponse:
        """Genera una risposta completa (non in streaming)."""
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        
        # Accumula tutti i chunk
        complete_content = ""
        async for chunk in provider.stream_completion(messages, settings):
            complete_content += chunk
        
        # Crea la risposta completa
        response = ChatCompletionResponse(
            id=completion_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=complete_content),
                    finish_reason="stop"
                )
            ]
        )
        
        return response
    
    def get_app(self) -> FastAPI:
        """Restituisce l'istanza dell'app FastAPI."""
        return self.app
