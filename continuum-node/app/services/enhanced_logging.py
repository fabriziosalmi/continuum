import logging
import json
import time
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
import threading
from collections import defaultdict, deque


@dataclass
class RequestMetric:
    """Metrica per una singola richiesta."""

    timestamp: float
    endpoint: str
    method: str
    status_code: int
    response_time: float
    user_token: str
    model_used: str = ""
    tokens_used: int = 0
    error_message: str = ""


class MetricsCollector:
    """Raccoglie e gestisce le metriche del sistema."""

    def __init__(self, max_metrics: int = 10000):
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.model_usage = defaultdict(int)
        self.user_activity = defaultdict(int)
        self.error_counts = defaultdict(int)
        self._lock = threading.Lock()
        self.start_time = time.time()

    def record_request(self, metric: RequestMetric) -> None:
        """Registra una metrica di richiesta."""
        with self._lock:
            self.metrics.append(metric)

            # Aggiorna contatori
            if metric.model_used:
                self.model_usage[metric.model_used] += 1

            self.user_activity[metric.user_token] += 1

            if metric.status_code >= 400:
                self.error_counts[f"{metric.status_code}_{metric.endpoint}"] += 1

    def get_summary(self) -> Dict[str, Any]:
        """Restituisce un riassunto delle metriche."""
        with self._lock:
            current_time = time.time()
            uptime = current_time - self.start_time

            # Calcola metriche nell'ultima ora
            hour_ago = current_time - 3600
            recent_metrics = [m for m in self.metrics if m.timestamp > hour_ago]

            return {
                "uptime_seconds": uptime,
                "total_requests": len(self.metrics),
                "requests_last_hour": len(recent_metrics),
                "average_response_time": sum(m.response_time for m in recent_metrics)
                / len(recent_metrics)
                if recent_metrics
                else 0,
                "model_usage": dict(self.model_usage),
                "top_users": dict(list(self.user_activity.items())[:10]),
                "error_summary": dict(self.error_counts),
                "requests_per_minute": len(
                    [m for m in recent_metrics if m.timestamp > current_time - 60]
                ),
            }

    def get_detailed_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Restituisce metriche dettagliate."""
        with self._lock:
            return [asdict(metric) for metric in list(self.metrics)[-limit:]]


class EnhancedLogger:
    """Logger migliorato con strutturazione JSON."""

    def __init__(self, name: str = "continuum-node"):
        self.logger = logging.getLogger(name)
        self.metrics = MetricsCollector()

        # Configura handler se non già configurato
        if not self.logger.handlers:
            self._setup_logging()

    def _setup_logging(self):
        """Configura il logging strutturato."""
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler (se la directory esiste)
        try:
            import os

            log_dir = "/app/logs"
            if os.path.exists(log_dir) or os.makedirs(log_dir, exist_ok=True):
                file_handler = logging.FileHandler(f"{log_dir}/continuum-node.log")
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
        except Exception:
            pass  # Ignora errori di setup file logging

        self.logger.setLevel(logging.INFO)

    def log_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        user_token: str,
        **kwargs,
    ):
        """Logga una richiesta e registra le metriche."""

        metric = RequestMetric(
            timestamp=time.time(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            user_token=user_token[:8] + "..." if user_token else "anonymous",
            model_used=kwargs.get("model_used", ""),
            tokens_used=kwargs.get("tokens_used", 0),
            error_message=kwargs.get("error_message", ""),
        )

        self.metrics.record_request(metric)

        # Log strutturato
        log_data = {
            "type": "request",
            "endpoint": endpoint,
            "method": method,
            "status": status_code,
            "response_time_ms": round(response_time * 1000, 2),
            "user": user_token[:8] + "..." if user_token else "anonymous",
        }

        if kwargs.get("model_used"):
            log_data["model"] = kwargs["model_used"]

        if status_code >= 400:
            self.logger.error(f"Request failed: {json.dumps(log_data)}")
        else:
            self.logger.info(f"Request completed: {json.dumps(log_data)}")

    def log_websocket_event(self, event: str, user_token: str, **kwargs):
        """Logga eventi WebSocket."""
        log_data = {
            "type": "websocket",
            "event": event,
            "user": user_token[:8] + "..." if user_token else "anonymous",
            **kwargs,
        }
        self.logger.info(f"WebSocket event: {json.dumps(log_data)}")

    def log_model_operation(
        self, operation: str, model: str, user_token: str, **kwargs
    ):
        """Logga operazioni sui modelli."""
        log_data = {
            "type": "model_operation",
            "operation": operation,
            "model": model,
            "user": user_token[:8] + "..." if user_token else "anonymous",
            **kwargs,
        }
        self.logger.info(f"Model operation: {json.dumps(log_data)}")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Restituisce il riassunto delle metriche."""
        return self.metrics.get_summary()

    def get_detailed_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Restituisce metriche dettagliate."""
        return self.metrics.get_detailed_metrics(limit)


# Istanza globale del logger
enhanced_logger = EnhancedLogger()
