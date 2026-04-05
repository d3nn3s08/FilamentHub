"""
Bambu Lab Authentication Service
================================
Authentifizierung mit der Bambu Lab Cloud API.
Unterstützt Email-Verifikation (2FA).

Basiert auf: https://github.com/coelacant1/Bambu-Lab-Cloud-API

Flow:
1. Login mit Email + Passwort
2. Falls 2FA: Email mit 6-stelligem Code wird gesendet
3. Code eingeben → Access Token erhalten
"""

import aiohttp
import asyncio
import logging
import json
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("bambu_auth")


class AuthRegion(Enum):
    """Bambu Lab API Regionen"""
    GLOBAL = "https://api.bambulab.com"
    CHINA = "https://api.bambulab.cn"


class LoginState(Enum):
    """Status des Login-Prozesses"""
    SUCCESS = "success"
    NEED_VERIFICATION_CODE = "need_verification_code"
    NEED_TFA = "need_tfa"
    FAILED = "failed"


@dataclass
class LoginResult:
    """Ergebnis eines Login-Versuchs"""
    state: LoginState
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    tfa_key: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[str] = None  # ISO-Datetime UTC, berechnet aus expiresIn oder 30-Tage-Fallback


def extract_jwt_expiry(token: str) -> Optional[str]:
    """
    Versucht das Ablaufdatum (exp) aus einem JWT-Token zu lesen.
    Bambu-Tokens sind KEINE JWTs – diese Funktion gibt None zurück.

    Returns:
        ISO-Datetime-String (UTC) oder None falls nicht parsebar
    """
    try:
        import base64
        from datetime import datetime, timezone
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
    except Exception:
        pass
    return None


def compute_token_expiry(expires_in_seconds: Optional[int] = None) -> str:
    """
    Berechnet den Token-Ablaufzeitpunkt.
    Bambu-Tokens sind opak (kein JWT) – wir nutzen expiresIn aus der API-Response.

    Laut OpenBambuAPI-Dokumentation liefert Bambu Lab: expiresIn = 7776000s = 90 Tage.
    Quelle: https://github.com/Doridian/OpenBambuAPI/blob/main/cloud-http.md

    Args:
        expires_in_seconds: Laufzeit in Sekunden aus der API-Response (optional)

    Returns:
        ISO-Datetime-String (UTC)
    """
    from datetime import datetime, timezone, timedelta
    # Bambu gibt 7776000s (90 Tage) zurück. Fallback ebenfalls 90 Tage.
    seconds = expires_in_seconds if expires_in_seconds and expires_in_seconds > 0 else 90 * 24 * 3600
    return (datetime.now(tz=timezone.utc) + timedelta(seconds=seconds)).isoformat()


class BambuAuthService:
    """
    Service für Bambu Lab Cloud Authentifizierung.

    Usage:
        auth = BambuAuthService(region="eu")

        # Schritt 1: Login starten
        result = await auth.login("email@example.com", "password")

        if result.state == LoginState.NEED_VERIFICATION_CODE:
            # Schritt 2: Code per Email erhalten und eingeben
            result = await auth.verify_code("email@example.com", "123456")

        if result.state == LoginState.SUCCESS:
            print(f"Token: {result.access_token}")
            print(f"User ID: {result.user_id}")
    """

    def __init__(self, region: str = "eu"):
        """
        Args:
            region: 'eu', 'us', 'global' oder 'cn'
        """
        if region.lower() in ("cn", "china"):
            self.base_url = AuthRegion.CHINA.value
        else:
            self.base_url = AuthRegion.GLOBAL.value

        self._session: Optional[aiohttp.ClientSession] = None
        self._pending_email: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy init der aiohttp Session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "bambu_network_agent/01.09.05.01",
                    "X-BBL-Client-Name": "OrcaSlicer",
                    "X-BBL-Client-Type": "slicer",
                    "X-BBL-Client-Version": "01.09.05.01",
                    "X-BBL-Language": "en-US",
                    "X-BBL-OS-Type": "windows",
                    "X-BBL-OS-Version": "10.0",
                    "X-BBL-Executable-info": "{}",
                    "X-BBL-Agent-OS-Type": "windows",
                }
            )
        return self._session

    async def close(self):
        """Schließt die Session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Führt einen API-Request aus."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        logger.debug(f"Auth Request: {method} {url}")

        try:
            async with session.request(method, url, json=data) as response:
                response_text = await response.text()

                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    logger.error(f"Auth: Invalid JSON response: {response_text[:200]}")
                    return {"error": "Invalid response", "raw": response_text}

                if response.status >= 400:
                    logger.error(f"Auth Error {response.status}: {result}")

                return result

        except aiohttp.ClientError as e:
            logger.error(f"Auth Network Error: {e}")
            return {"error": str(e)}

    async def login_with_tfa(self, email: str, password: str, tfa_code: str) -> LoginResult:
        """
        Kombinierter Login mit TFA-Code in einem Schritt.
        Macht Login + TFA-Verify direkt hintereinander ohne Verzögerung.

        Args:
            email: Bambu Lab Account Email
            password: Account Passwort
            tfa_code: 6-stelliger TOTP Code

        Returns:
            LoginResult mit Token bei Erfolg
        """
        self._pending_email = email
        print(f"[LOGIN+TFA] Starting combined login for {email}")

        # Schritt 1: Login um tfaKey zu bekommen
        login_data = {
            "account": email,
            "password": password,
        }

        login_result = await self._request("POST", "/v1/user-service/user/login", login_data)
        print(f"[LOGIN+TFA] Login response: {login_result}")

        login_type = login_result.get("loginType")

        if login_type != "tfa":
            # Kein TFA erforderlich oder direkter Login
            if login_result.get("accessToken"):
                return self._parse_token_response(login_result)
            else:
                return LoginResult(
                    state=LoginState.FAILED,
                    message=login_result.get("message") or "Login fehlgeschlagen (kein TFA)",
                )

        # Schritt 2: SOFORT TFA verifizieren (ohne Verzögerung!)
        tfa_key = login_result.get("tfaKey")
        print(f"[LOGIN+TFA] Got tfaKey: {tfa_key}, verifying immediately...")

        # Versuche verschiedene Kombinationen
        tfa_variants = [
            # Variante 1: tfaKey + tfaCode (Dokumentation)
            {"tfaKey": tfa_key, "tfaCode": tfa_code},
            # Variante 2: account + tfaKey + tfaCode
            {"account": email, "tfaKey": tfa_key, "tfaCode": tfa_code},
            # Variante 3: tfaKey + code
            {"tfaKey": tfa_key, "code": tfa_code},
            # Variante 4: account + tfaKey + code
            {"account": email, "tfaKey": tfa_key, "code": tfa_code},
        ]

        tfa_result = None
        for i, tfa_data in enumerate(tfa_variants):
            print(f"[LOGIN+TFA] Trying TFA variant {i+1}: {list(tfa_data.keys())}")
            tfa_result = await self._request("POST", "/v1/user-service/user/login", tfa_data)
            print(f"[LOGIN+TFA] Response: {tfa_result}")

            # Erfolg?
            if tfa_result.get("accessToken") or tfa_result.get("token"):
                print(f"[LOGIN+TFA] SUCCESS with variant {i+1}!")
                break

            # Bei "expired" sofort abbrechen - Code ist ungültig
            error = str(tfa_result.get("error", ""))
            if "expired" in error.lower() or "does not exist" in error.lower():
                print(f"[LOGIN+TFA] Code expired/invalid, stopping.")
                break

        # Token gefunden?
        access_token = tfa_result.get("accessToken") or tfa_result.get("token")
        if access_token:
            print(f"[LOGIN+TFA] SUCCESS! Token received.")
            if not tfa_result.get("accessToken") and tfa_result.get("token"):
                tfa_result["accessToken"] = tfa_result["token"]
            return self._parse_token_response(tfa_result)

        # Fehler
        error_msg = tfa_result.get("error") or tfa_result.get("message") or "TFA fehlgeschlagen"
        print(f"[LOGIN+TFA] FAILED: {error_msg}")
        return LoginResult(
            state=LoginState.FAILED,
            message=error_msg,
        )

    async def login(self, email: str, password: str) -> LoginResult:
        """
        Startet den Login-Prozess mit Email und Passwort.

        Args:
            email: Bambu Lab Account Email
            password: Account Passwort

        Returns:
            LoginResult mit Status und ggf. Token
        """
        self._pending_email = email

        data = {
            "account": email,
            "password": password,
        }

        result = await self._request("POST", "/v1/user-service/user/login", data)

        # Debug: Log full response
        logger.info(f"Auth: Login response keys: {list(result.keys())}")
        logger.debug(f"Auth: Full login response: {result}")

        # Check for errors
        if "error" in result:
            return LoginResult(
                state=LoginState.FAILED,
                message=result.get("error", "Unknown error"),
            )

        # Check login type
        login_type = result.get("loginType")

        if login_type == "verifyCode":
            # Email-Verifikation erforderlich
            logger.info("Auth: Email verification required")

            # Verifikationscode anfordern
            await self._request_verification_code(email)

            return LoginResult(
                state=LoginState.NEED_VERIFICATION_CODE,
                message="Verifikationscode wurde per Email gesendet",
            )

        elif login_type == "tfa":
            # 2FA (TOTP) erforderlich
            tfa_key = result.get("tfaKey")
            logger.info(f"Auth: TFA required, tfaKey={tfa_key[:20] if tfa_key else 'NONE'}...")
            logger.debug(f"Auth: Full TFA response: {result}")
            return LoginResult(
                state=LoginState.NEED_TFA,
                tfa_key=tfa_key,
                message="2FA Code erforderlich",
            )

        elif result.get("accessToken"):
            # Direkter Login erfolgreich
            logger.info("Auth: Login successful")
            return self._parse_token_response(result)

        else:
            # Unbekannter Status
            message = result.get("message") or result.get("msg") or "Login fehlgeschlagen"
            logger.warning(f"Auth: Unknown response: {result}")
            return LoginResult(
                state=LoginState.FAILED,
                message=message,
            )

    async def _request_verification_code(self, email: str) -> bool:
        """Fordert einen Verifikationscode per Email an."""
        data = {
            "email": email,
            "type": "codeLogin",
        }

        result = await self._request(
            "POST",
            "/v1/user-service/user/sendemail/code",
            data
        )

        success = result.get("success", False) or result.get("code") == 0
        if success:
            logger.info(f"Auth: Verification code sent to {email}")
        else:
            logger.warning(f"Auth: Failed to send verification code: {result}")

        return success

    async def verify_code(self, email: str, code: str) -> LoginResult:
        """
        Verifiziert den Email-Code und schließt den Login ab.

        Args:
            email: Email-Adresse
            code: 6-stelliger Verifikationscode aus der Email

        Returns:
            LoginResult mit Token bei Erfolg
        """
        data = {
            "account": email,
            "code": code,
        }

        result = await self._request("POST", "/v1/user-service/user/login", data)

        if result.get("accessToken"):
            logger.info("Auth: Code verification successful")
            return self._parse_token_response(result)
        else:
            message = result.get("message") or result.get("msg") or "Code ungültig"
            logger.warning(f"Auth: Code verification failed: {result}")
            return LoginResult(
                state=LoginState.FAILED,
                message=message,
            )

    async def verify_tfa(self, tfa_key: str, tfa_code: str, email: str = None, password: str = None) -> LoginResult:
        """
        Verifiziert den 2FA TOTP Code.

        Args:
            tfa_key: Key aus dem ersten Login-Response
            tfa_code: 6-stelliger TOTP Code aus Authenticator App
            email: Email-Adresse
            password: Passwort (optional, für combined login)

        Returns:
            LoginResult mit Token bei Erfolg
        """
        logger.info(f"Auth: TFA verify with tfaKey={tfa_key}, code={tfa_code}, email={email}")

        # Versuche mehrere Payload-Varianten
        payloads = [
            # Variante 1: tfaKey + code (wie vorher getestet)
            {"tfaKey": tfa_key, "code": tfa_code},
            # Variante 2: tfaKey + tfaCode
            {"tfaKey": tfa_key, "tfaCode": tfa_code},
        ]

        for i, data in enumerate(payloads):
            print(f"[TFA VERIFY] Trying payload variant {i+1}: {data}")

            result = await self._request("POST", "/v1/user-service/user/login", data)
            print(f"[TFA VERIFY] Response: {result}")

            # Token gefunden?
            access_token = result.get("accessToken") or result.get("token")
            if access_token:
                logger.info("Auth: TFA verification successful!")
                print(f"[TFA VERIFY] SUCCESS! Token received.")
                if not result.get("accessToken") and result.get("token"):
                    result["accessToken"] = result["token"]
                return self._parse_token_response(result)

            # Wenn "expired" - tfaKey ist abgelaufen, nicht weiterprobieren
            error_msg = result.get("error") or result.get("message") or ""
            if "expired" in str(error_msg).lower() or "does not exist" in str(error_msg).lower():
                print(f"[TFA VERIFY] tfaKey expired, stopping.")
                return LoginResult(
                    state=LoginState.FAILED,
                    message="Der tfaKey ist abgelaufen. Bitte Login erneut starten und den Code SOFORT eingeben.",
                )

        # Fehler auswerten
        error_msg = (
            result.get("error") or
            result.get("message") or
            result.get("msg") or
            result.get("error_msg") or
            "TFA Code ungültig"
        )

        logger.warning(f"Auth: TFA failed - {error_msg}")
        print(f"[TFA VERIFY] FAILED: {error_msg}")

        return LoginResult(
            state=LoginState.FAILED,
            message=error_msg,
        )

    def _parse_token_response(self, result: Dict) -> LoginResult:
        """Parst die Token-Response."""
        access_token = result.get("accessToken")
        refresh_token = result.get("refreshToken")

        # User ID aus Token extrahieren (JWT Payload)
        user_id = None
        username = None

        if access_token:
            try:
                # JWT hat 3 Teile, der mittlere ist der Payload (Base64)
                import base64
                parts = access_token.split(".")
                if len(parts) >= 2:
                    # Padding hinzufügen falls nötig
                    payload_b64 = parts[1]
                    padding = 4 - len(payload_b64) % 4
                    if padding != 4:
                        payload_b64 += "=" * padding

                    payload_json = base64.urlsafe_b64decode(payload_b64)
                    payload = json.loads(payload_json)

                    user_id = str(payload.get("user_id") or payload.get("uid") or payload.get("sub", ""))
                    username = payload.get("email") or payload.get("username")

                    logger.debug(f"Auth: Parsed user_id={user_id} from token")

            except Exception as e:
                logger.warning(f"Auth: Could not parse JWT payload: {e}")

        # Fallback: User ID aus Response
        if not user_id:
            user_id = str(result.get("user_id") or result.get("userId") or "")

        # Ablaufzeit berechnen: Bambu-Tokens sind opak (keine JWTs), daher aus expiresIn-Feld
        # oder 30-Tage-Fallback
        expires_in = result.get("expiresIn") or result.get("expires_in")
        try:
            expires_in_int = int(expires_in) if expires_in is not None else None
        except (TypeError, ValueError):
            expires_in_int = None
        expires_at = compute_token_expiry(expires_in_int)
        logger.info(f"Auth: Token-Ablaufzeit berechnet: {expires_at} (expiresIn={expires_in})")

        return LoginResult(
            state=LoginState.SUCCESS,
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user_id,
            username=username,
            expires_at=expires_at,
        )

    async def refresh_access_token(self, refresh_token: str) -> LoginResult:
        """
        Versucht den Access Token mit dem Refresh Token zu erneuern.

        ⚠️ HINWEIS (Stand 2025): Laut OpenBambuAPI-Dokumentation gibt der Refresh-Endpunkt
        von Bambu Lab immer 401 zurück und ist daher nicht funktionsfähig.
        Zusätzlich ist refreshToken == accessToken (gleicher Wert, gleiche Gültigkeit).
        Quelle: https://github.com/Doridian/OpenBambuAPI/blob/main/cloud-http.md

        Token-Laufzeit: 90 Tage (expiresIn: 7776000s)
        Nach Ablauf ist ein manueller Re-Login erforderlich.

        Args:
            refresh_token: Der gespeicherte Refresh Token

        Returns:
            LoginResult – i.d.R. FAILED da Endpoint nicht funktioniert
        """
        logger.info("Auth: Versuche Token-Refresh (Hinweis: Bambu-Refresh-Endpoint gibt 401 zurück)...")

        result = await self._request(
            "POST",
            "/v1/user-service/user/refreshtoken",
            {"refreshToken": refresh_token}
        )

        logger.debug(f"Auth: Refresh Token Response: {list(result.keys())}")

        if result.get("accessToken"):
            logger.info("Auth: Token-Refresh unerwartet erfolgreich!")
            return self._parse_token_response(result)

        error_msg = result.get("error") or result.get("message") or "Token-Refresh fehlgeschlagen (Endpoint deaktiviert)"
        logger.warning(f"Auth: Token-Refresh fehlgeschlagen (erwartet – Bambu-Endpoint deaktiviert): {error_msg}")
        return LoginResult(
            state=LoginState.FAILED,
            message=f"Automatischer Token-Refresh nicht möglich. Bitte erneut einloggen.",
        )

    async def validate_token(self, access_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Prüft ob ein Token noch gültig ist.

        Args:
            access_token: Der zu prüfende Token

        Returns:
            (is_valid, user_info)
        """
        session = await self._get_session()

        # Temporär Auth Header setzen
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with session.get(
                f"{self.base_url}/v1/user-service/my/profile",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return True, data
                elif response.status == 401:
                    return False, None
                else:
                    logger.warning(f"Auth: Token validation returned {response.status}")
                    return False, None

        except Exception as e:
            logger.error(f"Auth: Token validation error: {e}")
            return False, None


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

async def bambu_login(
    email: str,
    password: str,
    region: str = "eu"
) -> LoginResult:
    """
    Convenience-Funktion für einfachen Login.

    Returns:
        LoginResult - prüfe state für nächsten Schritt
    """
    auth = BambuAuthService(region=region)
    try:
        return await auth.login(email, password)
    finally:
        await auth.close()


async def bambu_verify_code(
    email: str,
    code: str,
    region: str = "eu"
) -> LoginResult:
    """
    Convenience-Funktion für Code-Verifikation.

    Returns:
        LoginResult mit Token bei Erfolg
    """
    auth = BambuAuthService(region=region)
    try:
        return await auth.verify_code(email, code)
    finally:
        await auth.close()
