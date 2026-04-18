"""
Token Encryption Service
========================
Sichere Verschluesselung von API Tokens fuer die Bambu Cloud Integration.

Verwendet Fernet (symmetric encryption) aus der cryptography library.
Der Encryption Key wird aus einer Umgebungsvariable oder einer generierten
Key-Datei geladen.
"""
import os
import logging
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("token_encryption")

KEY_FILE_PATH = Path(__file__).parent.parent.parent / "data" / ".encryption_key"
ENV_KEY_NAME = "FILAMENTHUB_ENCRYPTION_KEY"


class TokenEncryptionService:
    """
    Service fuer sichere Token-Verschluesselung.

    Verwendung:
        service = TokenEncryptionService()
        encrypted = service.encrypt("my_secret_token")
        decrypted = service.decrypt(encrypted)
    """

    def __init__(self):
        self._fernet: Optional[Fernet] = None
        self._key: Optional[bytes] = None

    def _get_or_create_key(self) -> bytes:
        """
        Laedt oder erstellt den Encryption Key.

        Prioritaet:
        1. Umgebungsvariable
        2. Key-Datei
        3. Neuen Key generieren und speichern
        """
        env_key = os.environ.get(ENV_KEY_NAME)
        if env_key:
            logger.info("Encryption Key aus Umgebungsvariable geladen")
            return env_key.encode("utf-8")

        if KEY_FILE_PATH.exists():
            try:
                key = KEY_FILE_PATH.read_bytes()
                logger.info(f"Encryption Key aus {KEY_FILE_PATH} geladen")
                return key
            except Exception as e:
                logger.warning(f"Konnte Key-Datei nicht lesen: {e}")

        logger.info("Generiere neuen Encryption Key...")
        key = Fernet.generate_key()

        try:
            KEY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            KEY_FILE_PATH.write_bytes(key)
            try:
                os.chmod(KEY_FILE_PATH, 0o600)
            except Exception:
                pass
            logger.info(f"Encryption Key gespeichert in {KEY_FILE_PATH}")
        except Exception as e:
            logger.error(f"Konnte Key-Datei nicht speichern: {e}")

        return key

    def _get_fernet(self) -> Fernet:
        """Gibt die Fernet-Instanz zurueck (lazy init)."""
        if self._fernet is None:
            self._key = self._get_or_create_key()
            self._fernet = Fernet(self._key)
        return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """Verschluesselt einen String."""
        if not plaintext:
            return ""

        fernet = self._get_fernet()
        encrypted = fernet.encrypt(plaintext.encode("utf-8"))
        return encrypted.decode("utf-8")

    def decrypt(self, encrypted_text: str) -> str:
        """Entschluesselt einen String."""
        if not encrypted_text:
            return ""

        try:
            fernet = self._get_fernet()
            decrypted = fernet.decrypt(encrypted_text.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken:
            logger.error("Entschluesselung fehlgeschlagen - ungueltiger Token oder Key")
            raise TokenDecryptionError("Ungueltiger Token oder falscher Encryption Key")
        except Exception as e:
            logger.error(f"Entschluesselungsfehler: {e}")
            raise TokenDecryptionError(f"Entschluesselungsfehler: {e}")

    def is_encrypted(self, text: str) -> bool:
        """Prueft ob ein Text verschluesselt aussieht."""
        if not text:
            return False
        return text.startswith("gAAAAA")

    def rotate_key(self, new_key: Optional[bytes] = None) -> bytes:
        """
        Rotiert den Encryption Key.

        ACHTUNG: Nach Key-Rotation muessen alle gespeicherten
        Tokens neu verschluesselt werden!
        """
        if new_key is None:
            new_key = Fernet.generate_key()

        try:
            KEY_FILE_PATH.write_bytes(new_key)
            os.chmod(KEY_FILE_PATH, 0o600)
        except Exception:
            pass

        self._fernet = None
        self._key = None

        logger.warning("Encryption Key wurde rotiert - alle Tokens muessen neu verschluesselt werden!")

        return new_key


class TokenDecryptionError(Exception):
    """Exception fuer Entschluesselungsfehler"""


_encryption_service: Optional[TokenEncryptionService] = None


def get_token_encryption_service() -> TokenEncryptionService:
    """Gibt die Singleton-Instanz des TokenEncryptionService zurueck."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = TokenEncryptionService()
    return _encryption_service


def encrypt_token(plaintext: str) -> str:
    """Shortcut fuer Token-Verschluesselung."""
    return get_token_encryption_service().encrypt(plaintext)


def decrypt_token(encrypted_text: str) -> str:
    """Shortcut fuer Token-Entschluesselung."""
    return get_token_encryption_service().decrypt(encrypted_text)
