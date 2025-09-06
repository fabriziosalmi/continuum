import asyncio
import logging
from typing import Optional
from .protocol import ContinuumProtocol
from ..services.auth_manager import AuthManager
from ..services.model_router import ModelRouter

logger = logging.getLogger(__name__)


class ContinuumTCPServer:
    """Server TCP per il Continuum Protocol."""

    def __init__(self, auth_manager: AuthManager, model_router: ModelRouter) -> None:
        self.auth_manager = auth_manager
        self.model_router = model_router
        self.server: Optional[asyncio.Server] = None

    async def start_server(self, host: str = "0.0.0.0", port: int = 8989) -> None:
        """
        Avvia il server TCP.

        Args:
            host: Indirizzo IP su cui ascoltare
            port: Porta su cui ascoltare
        """
        self.server = await asyncio.start_server(self._handle_client, host, port)

        addr = self.server.sockets[0].getsockname()
        logger.info(f"Continuum TCP Server avviato su {addr[0]}:{addr[1]}")

    async def stop_server(self) -> None:
        """Ferma il server TCP."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Continuum TCP Server fermato")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Gestisce una connessione client.

        Args:
            reader: Stream reader per leggere dal client
            writer: Stream writer per scrivere al client
        """
        client_addr = writer.get_extra_info("peername")
        logger.info(f"Nuova connessione da {client_addr}")

        authenticated_user = None

        try:
            while True:
                # Legge il messaggio dal client
                try:
                    (
                        msg_type,
                        payload,
                    ) = await ContinuumProtocol.unpack_message_from_stream(reader)
                    logger.debug(f"Ricevuto messaggio {msg_type} da {client_addr}")
                except ConnectionError:
                    logger.info(f"Client {client_addr} ha chiuso la connessione")
                    break
                except ValueError as e:
                    logger.error(
                        f"Errore nel formato del messaggio da {client_addr}: {e}"
                    )
                    error_response = ContinuumProtocol.create_error_response(
                        "INVALID_FORMAT", str(e)
                    )
                    writer.write(error_response)
                    await writer.drain()
                    continue

                # Gestisce i diversi tipi di messaggio
                if msg_type == "AUTH":
                    await self._handle_auth(payload, writer, client_addr)
                    # Ricontrolla l'autenticazione dopo aver processato AUTH
                    if "token" in payload:
                        authenticated_user = self.auth_manager.authenticate(
                            payload["token"]
                        )

                elif msg_type == "COMP":
                    if not authenticated_user:
                        error_response = ContinuumProtocol.create_error_response(
                            "NOT_AUTHENTICATED",
                            "Must authenticate before making completion requests",
                        )
                        writer.write(error_response)
                        await writer.drain()
                        continue

                    await self._handle_completion(
                        payload, writer, authenticated_user, client_addr
                    )

                else:
                    logger.warning(
                        f"Tipo di messaggio sconosciuto '{msg_type}' da {client_addr}"
                    )
                    error_response = ContinuumProtocol.create_error_response(
                        "UNKNOWN_MESSAGE_TYPE", f"Unknown message type: {msg_type}"
                    )
                    writer.write(error_response)
                    await writer.drain()

        except Exception as e:
            logger.error(f"Errore nella gestione del client {client_addr}: {e}")

        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info(f"Connessione con {client_addr} chiusa")

    async def _handle_auth(
        self, payload: dict, writer: asyncio.StreamWriter, client_addr
    ) -> None:
        """
        Gestisce un messaggio di autenticazione.

        Args:
            payload: Payload del messaggio AUTH
            writer: Stream writer per rispondere al client
            client_addr: Indirizzo del client
        """
        try:
            token = payload.get("token")
            if not token:
                response = ContinuumProtocol.create_auth_response(
                    False, "Missing token in authentication request"
                )
                writer.write(response)
                await writer.drain()
                return

            # Autentica l'utente
            user = self.auth_manager.authenticate(token)
            if user:
                user_info = self.auth_manager.get_user_info(token)
                response = ContinuumProtocol.create_auth_response(
                    True, "Authentication successful", user_info
                )
                logger.info(f"Autenticazione riuscita per {user.name} da {client_addr}")
            else:
                response = ContinuumProtocol.create_auth_response(
                    False, "Invalid authentication token"
                )
                logger.warning(f"Tentativo di autenticazione fallito da {client_addr}")

            writer.write(response)
            await writer.drain()

        except Exception as e:
            logger.error(f"Errore nell'autenticazione da {client_addr}: {e}")
            error_response = ContinuumProtocol.create_error_response(
                "AUTH_ERROR", "Internal authentication error"
            )
            writer.write(error_response)
            await writer.drain()

    async def _handle_completion(
        self, payload: dict, writer: asyncio.StreamWriter, user, client_addr
    ) -> None:
        """
        Gestisce un messaggio di richiesta completion.

        Args:
            payload: Payload del messaggio COMP
            writer: Stream writer per rispondere al client
            user: Utente autenticato
            client_addr: Indirizzo del client
        """
        try:
            model = payload.get("model")
            messages = payload.get("messages", [])
            settings = payload.get("settings", {})

            if not model:
                error_response = ContinuumProtocol.create_error_response(
                    "MISSING_MODEL", "Model field is required"
                )
                writer.write(error_response)
                await writer.drain()
                return

            # Verifica autorizzazione per il modello
            if not self.auth_manager.is_authorized(user.token, model):
                error_response = ContinuumProtocol.create_error_response(
                    "UNAUTHORIZED_MODEL", f"User not authorized to use model: {model}"
                )
                writer.write(error_response)
                await writer.drain()
                return

            # Ottiene il provider per il modello
            provider = self.model_router.get_provider_for_model(model)
            if not provider:
                error_response = ContinuumProtocol.create_error_response(
                    "MODEL_NOT_FOUND", f"Model not found: {model}"
                )
                writer.write(error_response)
                await writer.drain()
                return

            # Aggiunge il modello alle settings
            settings["model"] = model

            logger.info(f"Avviando completion per {user.name} con modello {model}")

            # Processa la completion in streaming
            try:
                async for chunk in provider.stream_completion(messages, settings):
                    if chunk:
                        chunk_message = ContinuumProtocol.create_completion_chunk(
                            chunk, False
                        )
                        writer.write(chunk_message)
                        await writer.drain()

                # Invia il chunk finale
                final_message = ContinuumProtocol.create_completion_chunk("", True)
                writer.write(final_message)
                await writer.drain()

                logger.info(
                    f"Completion completata per {user.name} con modello {model}"
                )

            except Exception as e:
                logger.error(f"Errore nella generazione per {user.name}: {e}")
                error_response = ContinuumProtocol.create_error_response(
                    "GENERATION_ERROR", f"Error generating completion: {str(e)}"
                )
                writer.write(error_response)
                await writer.drain()

        except Exception as e:
            logger.error(f"Errore nella gestione completion da {client_addr}: {e}")
            error_response = ContinuumProtocol.create_error_response(
                "INTERNAL_ERROR", "Internal server error"
            )
            writer.write(error_response)
            await writer.drain()
