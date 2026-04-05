"""
Token Encryption Service
========================
Sichere Verschlüsselung von API Tokens für die Bambu Cloud Integration.

Verwendet Fernet (symmetric encryption) aus der cryptography library.
Der Encryption Key wird aus einer Umgebungsvariable oder einer generierten
Key-Datei geladen.
"""
import os
import base64
import logging
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("token_encryption")

# Pfad zur Key-Datei (wird automatisch erstellt falls nicht vorhanden)
KEY_FILE_PATH = Path(__file__).parent.parent.parent / "data" / ".encryption_key"

# Umgebungsvariable für den Key (optional, hat Vorrang)
ENV_KEY_NAME = "FILAMENTHUB_ENCRYPTION_KEY"

# Salt für Key-Derivation (konstant, da wir den Key nicht aus Passwort ableiten)
SALT = b"FilamentHub_Bambu_Cloud_2026"


class TokenEncryptionService:
    """
    Service für sichere Token-Verschlüsselung.

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
        Lädt oder erstellt den Encryption Key.

        Priorität:
        1. Umgebungsvariable
        2. Key-Datei
        3. Neuen Key generieren und speichern
        """
        # 1. Prüfe Umgebungsvariable
        env_key = os.environ.get(ENV_KEY_NAME)
        if env_key:
            try:
                key = base64.urlsafe_b64decode(env_key)
                logger.info("Encryption Key aus Umgebungsvariable geladen")
                return key
            except Exception as e:
                logger.warning(f"Ungültiger Key in Umgebungsvariable: {e}")

        # 2. Prüfe Key-Datei
        if KEY_FILE_PATH.exists():
            try:
                key = KEY_FILE_PATH.read_bytes()
                logger.info(f"Encryption Key aus {KEY_FILE_PATH} geladen")
                return key
            except Exception as e:
                logger.warning(f"Konnte Key-Datei nicht lesen: {e}")

        # 3. Generiere neuen Key
        logger.info("Generiere neuen Encryption Key...")
        key = Fernet.generate_key()

        # Speichere Key
        try:
            KEY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            KEY_FILE_PATH.write_bytes(key)
            # Setze Dateiberechtigungen (nur Besitzer lesen/schreiben)
            try:
                os.chmod(KEY_FILE_PATH, 0o600)
            except Exception:
                pass  # Windows hat andere Berechtigungen
            logger.info(f"Encryption Key gespeichert in {KEY_FILE_PATH}")
        except Exception as e:
            logger.error(f"Konnte Key-Datei nicht speichern: {e}")

        return key

    def _get_fernet(self) -> Fernet:
        """Gibt die Fernet-Instanz zurück (lazy init)."""
        if self._fernet is None:
            self._key = self._get_or_create_key()
            self._fernet = Fernet(self._key)
        return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """
        Verschlüsselt einen String.

        Args:
            plaintext: Der zu verschlüsselnde Text

        Returns:
            Base64-kodierter verschlüsselter Text
        """
        if not plaintext:
            return ""

        fernet = self._get_fernet()
        encrypted = fernet.encrypt(plaintext.encode("utf-8"))
        return encrypted.decode("utf-8")

    def decrypt(self, encrypted_text: str) -> str:
        """
        Entschlüsselt einen String.

        Args:
            encrypted_text: Der verschlüsselte Text (Base64)

        Returns:
            Der entschlüsselte Klartext

        Raises:
            TokenDecryptionError: Bei Entschlüsselungsfehlern
        """
        if not encrypted_text:
            return ""

        try:
            fernet = self._get_fernet()
            decrypted = fernet.decrypt(encrypted_text.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken:
            logger.error("Entschlüsselung fehlgeschlagen - ungültiger Token oder Key")
            raise TokenDecryptionError("Ungültiger Token oder falscher Encryption Key")
        except Exception as e:
            logger.error(f"Entschlüsselungsfehler: {e}")
            raise TokenDecryptionError(f"Entschlüsselungsfehler: {e}")

    def is_encrypted(self, text: str) -> bool:
        """
        Prüft ob ein Text verschlüsselt aussieht.
        Fernet-verschlüsselte Texte beginnen mit 'gAAAAA'.
        """
        if not text:
            return False
        return text.startswith("gAAAAA")

    def rotate_key(self, new_key: Optional[bytes] = None) -> bytes:
        """
        Rotiert den Encryption Key.

        ACHTUNG: Nach Key-Rotation müssen alle gespeicherten
        Tokens neu verschlüsselt werden!

        Args:
            new_key: Optional neuer Key, sonst wird einer generiert

        Returns:
            Der neue Key (Base64)
        """
        if new_key is None:
            new_key = Fernet.generate_key()

        # Speichere neuen Key
        try:
            KEY_FILE_PATH.write_bytes(new_key)
            os.chmod(KEY_FILE_PATH, 0o600)
        except Exception:
            pass

        # Reset Fernet
        self._fernet = None
        self._key = None

        logger.warning("Encryption Key wurde rotiert - alle Tokens müssen neu verschlüsselt werden!")

        return new_key


class TokenDecryptionError(Exception):
    """Exception für Entschlüsselungsfehler"""
    pass


# ============================================================
# SINGLETON INSTANCE
# ============================================================

_encryption_service: Optional[TokenEncryptionService] = None


def get_token_encryption_service() -> TokenEncryptionService:
    """
    Gibt die Singleton-Instanz des TokenEncryptionService zurück.
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = TokenEncryptionService()
    return _encryption_service


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def encrypt_token(plaintext: str) -> str:
    """Shortcut für Token-Verschlüsselung."""
    return get_token_encryption_service().encrypt(plaintext)


def decrypt_token(encrypted_text: str) -> str:
    """Shortcut für Token-Entschlüsselung."""
    return get_token_encryption_service().decrypt(encrypted_text)
