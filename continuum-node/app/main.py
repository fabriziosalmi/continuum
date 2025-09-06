import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
import uvicorn

# Import con gestione sia per esecuzione diretta che come modulo
try:
    from .services.auth_manager import AuthManager
    from .services.model_router import ModelRouter
    from .bridge.http_server import HTTPServer
    from .core.server import ContinuumTCPServer
except ImportError:
    # Fallback per esecuzione diretta
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.services.auth_manager import AuthManager
    from app.services.model_router import ModelRouter
    from app.bridge.http_server import HTTPServer
    from app.core.server import ContinuumTCPServer

# Configura il logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ContinuumNode:
    """Classe principale per il Continuum Node."""

    def __init__(self) -> None:
        self.auth_manager = AuthManager()
        self.model_router = ModelRouter()
        self.http_server: HTTPServer = None
        self.tcp_server: ContinuumTCPServer = None
        self.uvicorn_server = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Inizializza tutti i servizi."""
        logger.info("Inizializzazione Continuum Node...")

        # Percorsi dei file di configurazione
        config_dir = Path("/app/config")
        if not config_dir.exists():
            # Fallback per lo sviluppo locale
            config_dir = Path(__file__).parent.parent / "config"

        users_file = config_dir / "users.yml"
        models_file = config_dir / "models.yml"

        # Carica la configurazione degli utenti
        try:
            self.auth_manager.load_users(str(users_file))
        except Exception as e:
            logger.error(f"Errore nel caricamento degli utenti: {e}")
            sys.exit(1)

        # Carica la configurazione dei modelli
        try:
            self.model_router.load_models(str(models_file))
        except Exception as e:
            logger.error(f"Errore nel caricamento dei modelli: {e}")
            sys.exit(1)

        # Inizializza i server
        self.http_server = HTTPServer(self.auth_manager, self.model_router)
        self.tcp_server = ContinuumTCPServer(self.auth_manager, self.model_router)

        logger.info("Inizializzazione completata")

    async def start_servers(self) -> None:
        """Avvia tutti i server."""
        logger.info("Avvio dei server...")

        # Avvia il server TCP (opzionale)
        tcp_enabled = os.getenv("ENABLE_TCP_SERVER", "false").lower() == "true"
        if tcp_enabled:
            try:
                tcp_host = os.getenv("TCP_HOST", "0.0.0.0")
                tcp_port = int(os.getenv("TCP_PORT", "8989"))
                await self.tcp_server.start_server(tcp_host, tcp_port)
            except Exception as e:
                logger.error(f"Errore nell'avvio del server TCP: {e}")

        # Configura il server HTTP
        http_host = os.getenv("HTTP_HOST", "0.0.0.0")
        http_port = int(os.getenv("HTTP_PORT", "8080"))

        # Configura Uvicorn
        config = uvicorn.Config(
            app=self.http_server.get_app(),
            host=http_host,
            port=http_port,
            log_level="info",
            access_log=True,
        )

        self.uvicorn_server = uvicorn.Server(config)

        logger.info(f"Server HTTP avviato su {http_host}:{http_port}")

        # Avvia il server HTTP in modo asincrono
        await self.uvicorn_server.serve()

    async def stop_servers(self) -> None:
        """Ferma tutti i server."""
        logger.info("Arresto dei server...")

        # Ferma il server HTTP
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True

        # Ferma il server TCP
        if self.tcp_server:
            await self.tcp_server.stop_server()

        logger.info("Server fermati")

    def setup_signal_handlers(self) -> None:
        """Configura i gestori dei segnali per la shutdown graziosa."""

        def signal_handler(signum, frame):
            logger.info(f"Ricevuto segnale {signum}, iniziando shutdown...")
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main() -> None:
    """Funzione principale."""
    logger.info("Avvio Continuum Node...")

    # Crea l'istanza del nodo
    node = ContinuumNode()

    # Configura i gestori dei segnali
    node.setup_signal_handlers()

    try:
        # Inizializza il nodo
        await node.initialize()

        # Avvia i server
        server_task = asyncio.create_task(node.start_servers())

        # Aspetta il segnale di shutdown
        shutdown_task = asyncio.create_task(node.shutdown_event.wait())

        # Aspetta che uno dei task finisca
        done, pending = await asyncio.wait(
            [server_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancella i task pendenti
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Errore fatale: {e}")
        sys.exit(1)

    finally:
        # Ferma i server
        await node.stop_servers()
        logger.info("Continuum Node fermato")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown interrotto dall'utente")
    except Exception as e:
        logger.error(f"Errore nell'avvio: {e}")
        sys.exit(1)
