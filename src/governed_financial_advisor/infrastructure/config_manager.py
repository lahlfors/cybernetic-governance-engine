import os
import logging
from typing import Any, Optional

# Try importing Google Secret Manager, but don't fail if missing (local dev)
try:
    from google.cloud import secretmanager
    HAS_GSM = True
except ImportError:
    HAS_GSM = False

logger = logging.getLogger("Infrastructure.ConfigManager")

class ConfigManager:
    """
    Production-grade Configuration Manager.

    Strategy:
    1. Check Environment Variables (K8s Secrets injected as Env Vars are standard).
    2. If missing and ENV=production, attempt to fetch from Google Secret Manager.
    3. If local (and dotenv loaded), use that.

    This replaces direct `os.getenv` calls for sensitive keys.
    """

    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.env = os.getenv("ENV", "development").lower()
        self._gsm_client = None

    def _get_gsm_client(self):
        if not self._gsm_client and HAS_GSM:
            try:
                self._gsm_client = secretmanager.SecretManagerServiceClient()
            except Exception as e:
                logger.error(f"Failed to initialize Secret Manager client: {e}")
        return self._gsm_client

    def get(self, key: str, default: Any = None, secret_id: str = None) -> str:
        """
        Retrieves a configuration value.

        Args:
            key: The environment variable name (e.g., "BROKER_API_KEY").
            default: Default value if not found.
            secret_id: Optional. The specific Secret Manager ID if different from key.
                       If provided, and key is missing in Env, GSM is queried.
        """
        # 1. Try Environment Variable (Fastest, supports K8s Secrets)
        val = os.getenv(key)
        if val is not None:
            return val

        # 2. If Production and Secret ID provided, try GSM
        if self.env == "production" and secret_id and self.project_id:
            logger.info(f"Config: Fetching {key} from Secret Manager ({secret_id})...")
            client = self._get_gsm_client()
            if client:
                try:
                    name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"
                    response = client.access_secret_version(request={"name": name})
                    return response.payload.data.decode("UTF-8")
                except Exception as e:
                    logger.warning(f"Config: Failed to fetch {secret_id} from GSM: {e}")

        # 3. Return Default
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        val = self.get(key)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key)
        if val is None:
            return default
        return str(val).lower() in ("true", "1", "yes", "on")

# Global Instance
config_manager = ConfigManager()
