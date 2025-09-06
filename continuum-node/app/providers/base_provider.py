from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any

class BaseProvider(ABC):
    """Classe base astratta per tutti i provider di modelli AI."""

    @abstractmethod
    async def stream_completion(
        self, messages: List[Dict[str, str]], settings: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Metodo principale per lo streaming delle completion.
        
        Args:
            messages: Una lista di messaggi nel formato standard di chat.
            settings: Un dizionario di impostazioni (es. temperature, max_tokens).

        Yields:
            Stringhe (chunk) della risposta in streaming.
        """
        # Questo è un generatore asincrono astratto - le implementazioni concrete
        # devono implementare questo metodo con yield appropriati.
        if False:  # Pragma: no cover
            yield
