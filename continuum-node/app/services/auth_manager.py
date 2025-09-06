import yaml
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class User:
    """Rappresenta un utente del sistema."""
    token: str
    name: str
    permissions: List[str]
    rate_limit: str


class AuthManager:
    """Gestisce l'autenticazione e l'autorizzazione degli utenti."""
    
    def __init__(self) -> None:
        self.users: Dict[str, User] = {}
        # Rate limiting: token -> [timestamps]
        self.rate_limit_tracker: Dict[str, List[float]] = defaultdict(list)
    
    def load_users(self, path: str) -> None:
        """
        Carica gli utenti dal file YAML specificato.
        
        Args:
            path: Percorso del file users.yml
        """
        try:
            with open(path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                
            if 'users' not in config:
                raise ValueError("File di configurazione utenti non valido: manca la sezione 'users'")
            
            # Carica ogni utente nella cache
            for user_config in config['users']:
                user = User(
                    token=user_config['token'],
                    name=user_config['name'],
                    permissions=user_config.get('permissions', []),
                    rate_limit=user_config.get('rate_limit', '10/minute')
                )
                self.users[user.token] = user
                
            print(f"Caricati {len(self.users)} utenti dal file {path}")
            
        except FileNotFoundError:
            raise FileNotFoundError(f"File di configurazione utenti non trovato: {path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Errore nel parsing del file YAML: {e}")
        except KeyError as e:
            raise ValueError(f"Campo richiesto mancante nella configurazione utenti: {e}")
    
    def authenticate(self, token: str) -> Optional[User]:
        """
        Autentica un utente basandosi sul token.
        
        Args:
            token: Token di autenticazione dell'utente
            
        Returns:
            Oggetto User se il token è valido, None altrimenti
        """
        return self.users.get(token)
    
    def is_authorized(self, token: str, model_id: str) -> bool:
        """
        Controlla se un utente è autorizzato ad utilizzare un modello specifico.
        
        Args:
            token: Token di autenticazione dell'utente
            model_id: ID del modello da verificare
            
        Returns:
            True se l'utente è autorizzato, False altrimenti
        """
        user = self.authenticate(token)
        if not user:
            return False
        
        # Controlla se l'utente ha il permesso per questo modello
        return model_id in user.permissions
    
    def get_user_info(self, token: str) -> Optional[Dict[str, any]]:
        """
        Restituisce le informazioni dell'utente per un dato token.
        
        Args:
            token: Token di autenticazione dell'utente
            
        Returns:
            Dizionario con le informazioni dell'utente o None se non trovato
        """
        user = self.authenticate(token)
        if not user:
            return None
        
        return {
            "name": user.name,
            "permissions": user.permissions,
            "rate_limit": user.rate_limit
        }
    
    def _parse_rate_limit(self, rate_limit_str: str) -> tuple:
        """
        Parsa una stringa di rate limit nel formato 'N/timeunit'.
        
        Args:
            rate_limit_str: Stringa come "100/minute" o "10/hour"
            
        Returns:
            Tupla (limite, secondi_per_periodo)
        """
        try:
            limit_str, time_unit = rate_limit_str.split('/')
            limit = int(limit_str)
            
            time_multipliers = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400
            }
            
            seconds = time_multipliers.get(time_unit, 60)  # Default: minute
            return limit, seconds
        except (ValueError, KeyError):
            # Fallback sicuro
            return 10, 60
    
    def check_rate_limit(self, token: str) -> bool:
        """
        Controlla se un utente ha superato il rate limit.
        
        Args:
            token: Token di autenticazione dell'utente
            
        Returns:
            True se la richiesta è permessa, False se il rate limit è superato
        """
        user = self.authenticate(token)
        if not user:
            return False
        
        current_time = time.time()
        limit, period_seconds = self._parse_rate_limit(user.rate_limit)
        
        # Pulisce i timestamp vecchi
        cutoff_time = current_time - period_seconds
        self.rate_limit_tracker[token] = [
            timestamp for timestamp in self.rate_limit_tracker[token]
            if timestamp > cutoff_time
        ]
        
        # Controlla se il limite è stato superato
        if len(self.rate_limit_tracker[token]) >= limit:
            return False
        
        # Aggiunge il timestamp corrente
        self.rate_limit_tracker[token].append(current_time)
        return True
