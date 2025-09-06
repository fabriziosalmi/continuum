import yaml
from typing import Dict, Optional, List
from ..providers.base_provider import BaseProvider
from ..providers.ollama_provider import OllamaProvider
from ..providers.openai_provider import OpenAIProvider


class ModelRouter:
    """Gestisce il routing dei modelli ai provider appropriati."""
    
    def __init__(self) -> None:
        self.model_providers: Dict[str, BaseProvider] = {}
        self.model_configs: Dict[str, Dict] = {}
    
    def load_models(self, path: str) -> None:
        """
        Carica la configurazione dei modelli dal file YAML specificato.
        
        Args:
            path: Percorso del file models.yml
        """
        try:
            with open(path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                
            if 'models' not in config:
                raise ValueError("File di configurazione modelli non valido: manca la sezione 'models'")
            
            # Processa ogni modello configurato
            for model_config in config['models']:
                model_id = model_config['id']
                provider_type = model_config['provider']
                
                # Memorizza la configurazione del modello
                self.model_configs[model_id] = model_config
                
                # Crea l'istanza del provider appropriato
                provider_instance = self._create_provider(provider_type)
                if provider_instance:
                    self.model_providers[model_id] = provider_instance
                    print(f"Configurato modello '{model_id}' con provider '{provider_type}'")
                else:
                    print(f"Warning: Provider '{provider_type}' non supportato per il modello '{model_id}'")
            
            print(f"Caricati {len(self.model_providers)} modelli dal file {path}")
            
        except FileNotFoundError:
            raise FileNotFoundError(f"File di configurazione modelli non trovato: {path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Errore nel parsing del file YAML: {e}")
        except KeyError as e:
            raise ValueError(f"Campo richiesto mancante nella configurazione modelli: {e}")
    
    def _create_provider(self, provider_type: str) -> Optional[BaseProvider]:
        """
        Crea un'istanza del provider specificato.
        
        Args:
            provider_type: Tipo di provider da creare ('ollama', 'openai', ecc.)
            
        Returns:
            Istanza del provider o None se non supportato
        """
        try:
            if provider_type.lower() == "ollama":
                return OllamaProvider()
            elif provider_type.lower() == "openai":
                provider = OpenAIProvider()
                # Verifica che la chiave API sia disponibile
                if not provider.api_key:
                    print(f"Warning: OpenAI provider configurato ma OPENAI_API_KEY non trovata")
                    return None
                return provider
            else:
                print(f"Provider type '{provider_type}' non supportato")
                return None
        except Exception as e:
            print(f"Errore nella creazione del provider '{provider_type}': {e}")
            return None
    
    def get_provider_for_model(self, model_id: str) -> Optional[BaseProvider]:
        """
        Restituisce l'istanza del provider per un modello specifico.
        
        Args:
            model_id: ID del modello
            
        Returns:
            Istanza del provider se il modello è configurato, None altrimenti
        """
        return self.model_providers.get(model_id)
    
    def get_available_models(self) -> List[str]:
        """
        Restituisce la lista degli ID dei modelli disponibili.
        
        Returns:
            Lista degli ID dei modelli configurati
        """
        return list(self.model_providers.keys())
    
    def get_model_config(self, model_id: str) -> Optional[Dict]:
        """
        Restituisce la configurazione per un modello specifico.
        
        Args:
            model_id: ID del modello
            
        Returns:
            Dizionario di configurazione del modello o None se non trovato
        """
        return self.model_configs.get(model_id)
    
    def is_model_available(self, model_id: str) -> bool:
        """
        Controlla se un modello è disponibile e configurato.
        
        Args:
            model_id: ID del modello da verificare
            
        Returns:
            True se il modello è disponibile, False altrimenti
        """
        return model_id in self.model_providers
