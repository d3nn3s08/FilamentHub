"""
G-Code FTPS Service - Herunterladung und Parsing von G-Code Dateien
für Filament-Gewichtsberechnung von Bambu Lab Druckern

Features:
- FTPS-Verbindung zu Bambu Druckern (Port 990, TLS)
- Automatischer G-Code Download vom /cache Pfad  
- Parsing von Filament-Gewicht aus G-Code Kommentaren
"""

import socket
import ssl
import ftplib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile
import io

logger = logging.getLogger("services")


class SimpleFTPS:
    """
    Simple FTPS-Implementierung mit manuellen FTP-Befehlen über SSL-Socket
    Robust gegen selbstsignierte Zertifikate und langsame Connections
    """

    def __init__(self, timeout=120):
        # Timeout erhöht auf 120s für langsame SSL Handshakes
        self.timeout = timeout
        self.sock = None
        self.sock_file = None
        self.data_sock = None
        self.host = None
        self.port = 990
        self.logged_in = False
        # SSL context and session from control connection (for session reuse)
        self.ssl_context = None
        self.ssl_session = None
        
    def _make_ssl_ctx(self, variant: int = 0) -> ssl.SSLContext:
        """
        Erstellt SSL-Context in verschiedenen Kompatibilitaets-Varianten.
        Variante 0: Standard TLS 1.2+ (modern)
        Variante 1: TLS beliebig + SECLEVEL=1 (erlaubt schwaeche Ciphers, fuer X1C/alte Embedded-Geraete)
        Variante 2: TLS beliebig + SECLEVEL=0 + kein SNI-Hinweis
        """
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        if variant == 0:
            # Standard: TLS 1.2 minimum
            try:
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            except Exception:
                pass
        elif variant == 1:
            # Kompatibel: Alle TLS-Versionen, SECLEVEL=1 (erlaubt schwaeche DH-Parameter)
            try:
                ctx.minimum_version = ssl.TLSVersion.TLSv1
            except Exception:
                pass
            try:
                ctx.set_ciphers("DEFAULT@SECLEVEL=1")
            except Exception:
                pass
        else:
            # Maximal kompatibel: SECLEVEL=0, breite Cipher-Unterstuetzung
            try:
                ctx.minimum_version = ssl.TLSVersion.TLSv1
            except Exception:
                pass
            try:
                ctx.set_ciphers("DEFAULT@SECLEVEL=0")
            except Exception:
                try:
                    ctx.set_ciphers("HIGH:MEDIUM:!aNULL:!eNULL:@STRENGTH")
                except Exception:
                    pass

        return ctx

    def connect(self, host, port=990, retries=5):
        """Verbinde mit FTPS Server — versucht mehrere SSL-Varianten fuer maximale Kompatibilitaet"""
        self.host = host
        self.port = port

        last_error = None
        # SSL-Varianten: 0=Standard TLS1.2, 1=TLS1.0+ SECLEVEL=1, 2=TLS1.0+ SECLEVEL=0
        ssl_variants = [0, 1, 2]

        for attempt in range(retries):
            # Waehle SSL-Variante: erste Versuche mit Standard, spaetere mit Fallbacks
            variant = ssl_variants[min(attempt, len(ssl_variants) - 1)]
            ctx = self._make_ssl_ctx(variant)

            logger.debug(f"[FTPS] Connecting to {host}:{port} (attempt {attempt + 1}/{retries}, SSL-variant={variant})")

            try:
                # TCP-Verbindung
                raw_sock = socket.create_connection((host, port), timeout=self.timeout)

                # SSL Wrap — SNI-Hostname nur bei Standard-Variante
                sni_host = host if variant == 0 else None
                try:
                    self.sock = ctx.wrap_socket(raw_sock, server_hostname=sni_host)
                except ssl.SSLError as ssl_err:
                    raw_sock.close()
                    logger.warning(f"[FTPS] SSL handshake failed (attempt {attempt + 1}, variant={variant}): {ssl_err}")
                    last_error = ssl_err
                    if attempt < retries - 1:
                        import time
                        time.sleep(1)
                        continue
                    raise

                # File-Objekt fuer readline
                self.sock_file = self.sock.makefile('r', encoding='utf-8')

                # Welcome-Nachricht lesen
                resp = self.sock_file.readline().strip()
                logger.debug(f"[FTPS] Server welcome: {resp}")

                if not resp.startswith("220"):
                    self.sock.close()
                    raise Exception(f"Bad FTP welcome: {resp}")

                # SSL-Context + Session fuer Daten-Kanal speichern
                try:
                    self.ssl_context = ctx
                    self.ssl_session = getattr(self.sock, 'session', None)
                except Exception:
                    self.ssl_context = None
                    self.ssl_session = None

                logger.info(f"[FTPS] Verbunden mit {host}:{port} (SSL-Variante {variant})")
                return

            except socket.timeout as e:
                last_error = e
                logger.warning(f"[FTPS] Timeout (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(1)
                    continue
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"[FTPS] Fehler (attempt {attempt + 1}, variant={variant}): {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(1)
                    continue
                raise

        raise last_error or Exception("FTPS connection failed after all retries")
    
    def _send_cmd(self, cmd):
        """Sende FTP Befehl"""
        if not self.sock:
            raise RuntimeError("FTPS socket not connected")
        logger.debug(f"[FTPS] >> {cmd}")
        self.sock.sendall((cmd + "\r\n").encode('utf-8'))
        
    def _read_response(self):
        """Lese FTP Response"""
        if not self.sock_file:
            raise RuntimeError("FTPS socket file not initialized")
        response = self.sock_file.readline().strip()
        logger.debug(f"[FTPS] << {response}")
        return response
        
    def login(self, username, password):
        """Anmelden bei FTP"""
        # USER
        self._send_cmd(f"USER {username}")
        resp = self._read_response()
        if not resp.startswith("331"):
            raise Exception(f"USER failed: {resp}")
        
        # PASS
        self._send_cmd(f"PASS {password}")
        resp = self._read_response()
        if not resp.startswith("230"):
            raise Exception(f"LOGIN failed: {resp}")

        self.logged_in = True

        # PBSZ 0 + PROT P: Datenkanal-Schutz aktivieren (erforderlich fuer vsFTPd mit require_ssl_reuse)
        try:
            self._send_cmd("PBSZ 0")
            self._read_response()
        except Exception:
            pass
        try:
            self._send_cmd("PROT P")
            self._read_response()
        except Exception:
            pass

        logger.debug(f"[FTPS] Login successful (PROT P aktiv)")
    
    def cwd(self, dirname):
        """Change working directory"""
        self._send_cmd(f"CWD {dirname}")
        resp = self._read_response()
        if not resp.startswith("250"):
            raise Exception(f"CWD failed: {resp}")
    
    def list_dir(self, with_metadata=False):
        """
        LIST Verzeichnis

        Args:
            with_metadata: Wenn True, return Liste von Dicts mit Datei-Metadaten
                          Wenn False, return nur Liste von Dateinamen

        Returns:
            Liste von Dateinamen oder Liste von Dicts: [{name, size, mtime_str}, ...]
        """
        # Passive mode
        self._send_cmd("PASV")
        resp = self._read_response()
        if not resp.startswith("227"):
            raise Exception(f"PASV failed: {resp}")

        # Parse IP und Port aus Response
        # Format: "227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)"
        import re
        m = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', resp)
        if not m:
            raise Exception(f"Cannot parse PASV response: {resp}")

        h1, h2, h3, h4, p1, p2 = map(int, m.groups())
        data_host = f"{h1}.{h2}.{h3}.{h4}"
        data_port = (p1 << 8) + p2

        logger.debug(f"[FTPS] Passive mode: {data_host}:{data_port}")

        # Reuse SSL context/session from control connection
        ctx = getattr(self, 'ssl_context', None)
        if ctx is None:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        # Wenn PASV IP != control IP, override (NAT-Situation)
        if data_host != self.host:
            logger.debug(f"[FTPS] PASV returned different host {data_host}; overriding with {self.host}")
            data_host = self.host

        # TCP-Verbindung zum Datenport
        data_sock = socket.create_connection((data_host, data_port), timeout=min(self.timeout, 10))

        # vsFTPd require_ssl_reuse: Reihenfolge KRITISCH!
        # 1) LIST-Befehl zum Kontrollkanal senden BEVOR SSL-Handshake auf Datenkanal
        # 2) 150-Antwort lesen (Server oeffnet Datenkanal)
        # 3) DANN SSL-Handshake auf Datenkanal MIT Session-Reuse
        self._send_cmd("LIST")
        resp = self._read_response()
        if not resp.startswith("150"):
            try:
                data_sock.close()
            except Exception:
                pass
            raise Exception(f"LIST failed: {resp}")

        # SSL-Handshake auf Datenkanal — MIT session reuse (vsFTPd require_ssl_reuse=yes)
        import time
        session = getattr(self, 'ssl_session', None)
        try:
            data_ssl = ctx.wrap_socket(data_sock, server_hostname=self.host,
                                       session=session, do_handshake_on_connect=False)
        except TypeError:
            data_ssl = ctx.wrap_socket(data_sock, server_hostname=self.host,
                                       do_handshake_on_connect=False)
        data_ssl.settimeout(min(self.timeout, 10))
        t0 = time.time()
        try:
            data_ssl.do_handshake()
            logger.debug(f"[FTPS] Data TLS handshake OK in {time.time()-t0:.3f}s (reused={data_ssl.session_reused})")
        except Exception as e:
            logger.warning(f"[FTPS] Data TLS handshake failed after {time.time()-t0:.3f}s (LIST): {e}")
            try:
                data_ssl.close()
            except Exception:
                pass
            raise

        # Lese Dateiliste
        file_list = []
        raw_data = ""
        while True:
            data = data_ssl.recv(4096)
            if not data:
                break
            raw_data += data.decode('utf-8', errors='ignore')

        for line in raw_data.split('\n'):
            if not line.strip():
                continue

            parts = line.split()

            if with_metadata:
                # FTP LIST Format: perms links owner group size month day time/year filename...
                if len(parts) >= 9:
                    filename = " ".join(parts[8:])  # preserve spaces
                    try:
                        size = int(parts[4])
                    except (ValueError, IndexError):
                        size = 0
                    mtime_str = " ".join(parts[5:8])
                else:
                    # Fallback: treat entire line as filename if format unexpected
                    filename = line.strip()
                    size = 0
                    mtime_str = ""

                file_list.append({
                    "name": filename,
                    "size": size,
                    "mtime_str": mtime_str
                })
            else:
                # Nur Dateiname
                if len(parts) >= 9:
                    filename = " ".join(parts[8:])
                else:
                    filename = parts[-1] if parts else line.strip()
                file_list.append(filename)

        try:
            data_ssl.close()
        except Exception:
            pass

        # Lese abschluss
        resp = self._read_response()
        if not resp.startswith("226"):
            logger.warning(f"LIST end status: {resp}")

        return file_list
    
    def download_file(self, filename):
        """Download Datei und return Inhalt"""
        # Passive mode
        self._send_cmd("PASV")
        resp = self._read_response()
        if not resp.startswith("227"):
            raise Exception(f"PASV failed: {resp}")
        
        # Parse IP und Port
        import re
        m = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', resp)
        if not m:
            raise Exception(f"Cannot parse PASV response: {resp}")
        
        h1, h2, h3, h4, p1, p2 = map(int, m.groups())
        data_host = f"{h1}.{h2}.{h3}.{h4}"
        data_port = (p1 << 8) + p2
        
        logger.debug(f"[FTPS] Download passive mode: {data_host}:{data_port}")

        # Reuse SSL context/session from control connection
        ctx = getattr(self, 'ssl_context', None)
        if ctx is None:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        # Wenn PASV IP != control IP, override (NAT-Situation)
        if data_host != self.host:
            logger.debug(f"[FTPS] PASV returned different host {data_host}; overriding with {self.host}")
            data_host = self.host

        # TCP-Verbindung zum Datenport
        data_sock = socket.create_connection((data_host, data_port), timeout=min(self.timeout, 10))

        # vsFTPd require_ssl_reuse: Reihenfolge KRITISCH!
        # RETR-Befehl ZUERST, dann SSL-Handshake mit Session-Reuse
        self._send_cmd(f"RETR {filename}")
        resp = self._read_response()
        if not resp.startswith("150"):
            try:
                data_sock.close()
            except Exception:
                pass
            raise Exception(f"RETR failed: {resp}")

        # SSL-Handshake auf Datenkanal MIT session reuse
        import time
        session = getattr(self, 'ssl_session', None)
        try:
            data_ssl = ctx.wrap_socket(data_sock, server_hostname=self.host,
                                       session=session, do_handshake_on_connect=False)
        except TypeError:
            data_ssl = ctx.wrap_socket(data_sock, server_hostname=self.host,
                                       do_handshake_on_connect=False)
        data_ssl.settimeout(min(self.timeout, 10))
        t0 = time.time()
        try:
            data_ssl.do_handshake()
            logger.debug(f"[FTPS] Data TLS handshake OK in {time.time()-t0:.3f}s (reused={data_ssl.session_reused})")
        except Exception as e:
            logger.warning(f"[FTPS] Data TLS handshake failed after {time.time()-t0:.3f}s (RETR): {e}")
            try:
                data_ssl.close()
            except Exception:
                pass
            raise
        
        # Lese Dateiinhalt
        file_content = b""
        try:
            while True:
                data = data_ssl.recv(16384)
                if not data:
                    break
                file_content += data
        finally:
            try:
                data_ssl.close()
            except Exception:
                pass
        
        # Lese abschluss
        resp = self._read_response()
        if not resp.startswith("226"):
            logger.warning(f"RETR end status: {resp}")
        
        return file_content
    
    def quit(self):
        """Disconnect"""
        try:
            self._send_cmd("QUIT")
            self._read_response()
        except:
            pass
        
        if self.sock:
            try:
                self.sock.close()
            except:
                pass


class FTPLibFTPS:
    """
    Fallback-Client basierend auf ftplib.FTP_TLS.
    Versucht implicit FTPS (Port 990) indem der Control-Socket nach connect gewrappt wird.
    Liefert die gleiche minimale Schnittstelle wie `SimpleFTPS`:
    connect, login, cwd, list_dir(with_metadata), download_file, quit
    """
    def __init__(self, timeout=120):
        self.timeout = timeout
        self.conn: Optional[ftplib.FTP_TLS] = None

    def connect(self, host, port=990):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Erstelle FTP_TLS und verbinde
        self.conn = ftplib.FTP_TLS()
        # Standard connect; we'll wrap the socket for implicit FTPS
        self.conn.connect(host, port, timeout=self.timeout)
        try:
            # Versuche implizite TLS: wrap existing control socket
            sock = getattr(self.conn, 'sock', None)
            if sock is None:
                logger.debug("[FTPLIB] No underlying control socket to wrap for implicit FTPS")
            else:
                self.conn.sock = ctx.wrap_socket(sock, server_hostname=host)
                # Update file handle used von ftplib intern
                try:
                    self.conn.file = self.conn.sock.makefile('r', encoding=self.conn.encoding)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[FTPLIB] Implicit wrap failed: {e}")

    def login(self, username, password):
        if not self.conn:
            raise RuntimeError("FTPLibFTPS not connected")
        # Verwende ftplib login und aktiviere Schutz für Datenkanal
        self.conn.login(user=username, passwd=password)
        try:
            # Explicitly switch to protected data channel
            self.conn.prot_p()
        except Exception:
            pass

    def cwd(self, dirname):
        if not self.conn:
            raise RuntimeError("FTPLibFTPS not connected")
        self.conn.cwd(dirname)

    def list_dir(self, with_metadata=False):
        if not self.conn:
            raise RuntimeError("FTPLibFTPS not connected")
        lines = []
        try:
            self.conn.retrlines('LIST', callback=lines.append)
        except Exception as e:
            raise

        file_list = []
        for line in lines:
            parts = line.split()
            if with_metadata:
                if len(parts) >= 9:
                    filename = " ".join(parts[8:])
                    try:
                        size = int(parts[4])
                    except Exception:
                        size = 0
                    mtime_str = " ".join(parts[5:8])
                else:
                    filename = line.strip()
                    size = 0
                    mtime_str = ""
                file_list.append({"name": filename, "size": size, "mtime_str": mtime_str})
            else:
                if len(parts) >= 9:
                    filename = " ".join(parts[8:])
                else:
                    filename = parts[-1] if parts else line.strip()
                file_list.append(filename)

        return file_list

    def download_file(self, filename):
        if not self.conn:
            raise RuntimeError("FTPLibFTPS not connected")
        buf = io.BytesIO()
        try:
            self.conn.retrbinary(f"RETR {filename}", buf.write)
        except Exception as e:
            raise
        return buf.getvalue()

    def quit(self):
        try:
            if self.conn:
                try:
                    self.conn.quit()
                except Exception:
                    try:
                        self.conn.close()
                    except Exception:
                        pass
        except Exception:
            pass


class GcodeFTPService:
    """Service für G-Code Download und Parsing via FTPS"""

    def __init__(self, timeout=60):
        self.gcode_cache_dir = Path("data/gcode_cache")
        self.gcode_cache_dir.mkdir(parents=True, exist_ok=True)
        # Erhöhter Timeout für X1C (SSL Handshake kann langsam sein)
        # Default erhöhen auf 120s (überschreibbar beim Instanziieren)
        self.timeout = 120 if timeout == 60 else timeout

    def download_gcode_weight(
        self,
        printer_ip: str,
        api_key: str,
        task_id: str,
        gcode_filename: Optional[str] = None
    ) -> Optional[float]:
        """
        Lädt G-Code vom Bambu Drucker herunter und extrahiert Filament-Gewicht

        Args:
            printer_ip: IP-Adresse des A1 Mini
            api_key: FTPS Access Code (aus Drucker DB als api_key)
            task_id: Task ID für Logging (nicht für Dateinamen!)
            gcode_filename: Dateiname vom MQTT payload (z.B. "Würfel_plate_1.gcode")

        Returns:
            Filament-Gewicht in Gramm oder None
        """
        ftps = None
        try:
            # Standard Bambu FTP Credentials
            username = "bblp"
            password = api_key

            logger.info(
                f"[GCODE FTPS] Connecting to {printer_ip}:990 "
                f"for task_id={task_id}, filename={gcode_filename}"
            )

            # FTPS-Verbindung aufbauen mit detailliertem Logging
            try:
                ftps = SimpleFTPS(timeout=self.timeout)
                ftps.connect(printer_ip, 990)
                logger.info(f"[GCODE FTPS] FTPS connection established to {printer_ip}:990")
                ftps.login(username, password)
                logger.info(f"[GCODE FTPS] Login successful for user {username}")
                ftps.cwd("/cache")
                logger.debug(f"[GCODE FTPS] Changed to /cache directory")
            except Exception as conn_exc:
                logger.error(f"[GCODE FTPS] FTPS connection/login/cwd failed: {conn_exc}", exc_info=True)
                raise

            # Liste Dateien mit Metadaten auf
            try:
                file_list_simple = ftps.list_dir(with_metadata=False)
                file_list_meta = ftps.list_dir(with_metadata=True)
                try:
                    logger.debug(f"[GCODE FTPS] Files in /cache: {[f['name'] for f in file_list_meta[:10]]}")
                except Exception:
                    logger.debug("[GCODE FTPS] Files in /cache: (unable to render list)")
            except Exception as list_exc:
                logger.error(f"[GCODE FTPS] Error listing /cache directory: {list_exc}", exc_info=True)
                # Versuche Fallback mit ftplib.FTP_TLS
                try:
                    logger.info("[GCODE FTPS] Attempting ftplib.FTP_TLS fallback for listing")
                    try:
                        ftps.quit()
                    except Exception:
                        pass
                    ftps = FTPLibFTPS(timeout=self.timeout)
                    ftps.connect(printer_ip, 990)
                    ftps.login(username, password)
                    ftps.cwd("/cache")
                    file_list_simple = ftps.list_dir(with_metadata=False)
                    file_list_meta = ftps.list_dir(with_metadata=True)
                except Exception as fb_exc:
                    logger.error(f"[GCODE FTPS] ftplib fallback failed: {fb_exc}", exc_info=True)
                    raise

            # Haupt-Strategie: Nutze gcode_filename direkt vom MQTT
            downloaded_file = None

            if gcode_filename:
                filename_base = gcode_filename.replace(".gcode", "").replace(".3mf", "")
                candidates = [
                    gcode_filename,
                    f"{filename_base}.gcode",
                    f"{filename_base}.3mf",
                ]
                for candidate in candidates:
                    if candidate in file_list_simple:
                        downloaded_file = candidate
                        logger.info(f"[GCODE FTPS] Found exact match: {downloaded_file}")
                        break
                # Fuzzy-Match
                if not downloaded_file and len(filename_base) > 3:
                    base_normalized = (
                        filename_base.lower().replace(" ", "").replace("_", "").replace("-", "")
                    )
                    for file_info in file_list_meta:
                        filename = file_info["name"]
                        if not (filename.lower().endswith(".gcode") or filename.lower().endswith(".3mf")):
                            continue
                        filename_normalized = (
                            filename.lower().replace(" ", "").replace("_", "").replace("-", "").replace(".gcode", "")
                        )
                        if filename_normalized.startswith(base_normalized):
                            downloaded_file = filename
                            logger.warning(f"[GCODE FTPS] Using fuzzy match: {downloaded_file}")
                            break

            # Fallback: Title-basiertes Matching
            if not downloaded_file and gcode_filename:
                logger.warning(f"[GCODE FTPS] Could not find {gcode_filename}. Trying Title-based .3mf matching...")
                try:
                    downloaded_file = self._find_3mf_by_title(ftps, gcode_filename, file_list_meta)
                    if downloaded_file:
                        logger.info(f"[GCODE FTPS] ✓ Title-based match found: {downloaded_file}")
                except Exception as title_exc:
                    logger.error(f"[GCODE FTPS] Error in title-based .3mf matching: {title_exc}", exc_info=True)

            # Letzter Fallback: Neueste Datei
            if not downloaded_file:
                logger.warning(f"[GCODE FTPS] No match found. Looking for newest .gcode/.3mf file...")
                try:
                    gcode_files = [
                        f for f in file_list_meta
                        if f["name"].endswith(".gcode") or f["name"].endswith(".3mf")
                    ]
                    if gcode_files:
                        gcode_files_sorted = sorted(
                            gcode_files,
                            key=lambda x: x.get("mtime_str", ""),
                            reverse=True
                        )
                        downloaded_file = gcode_files_sorted[0]["name"]
                        logger.info(f"[GCODE FTPS] Using newest file: {downloaded_file} (modified: {gcode_files_sorted[0].get('mtime_str', 'unknown')})")
                    else:
                        logger.error(f"[GCODE FTPS] No .gcode files found in /cache")
                        ftps.quit()
                        return None
                except Exception as newest_exc:
                    logger.error(f"[GCODE FTPS] Error finding newest .gcode/.3mf file: {newest_exc}", exc_info=True)
                    ftps.quit()
                    return None

            # Download G-Code Datei
            try:
                logger.info(f"[GCODE FTPS] Downloading {downloaded_file}...")
                file_content = ftps.download_file(downloaded_file)
            except Exception as dl_exc:
                logger.error(f"[GCODE FTPS] Error downloading file {downloaded_file}: {dl_exc}", exc_info=True)
                # Wenn der primäre Client (SimpleFTPS) fehlschlägt, versuche ftplib Fallback
                try:
                    if not isinstance(ftps, FTPLibFTPS):
                        logger.info("[GCODE FTPS] Attempting ftplib.FTP_TLS fallback for download")
                        try:
                            ftps.quit()
                        except Exception:
                            pass
                        ftps = FTPLibFTPS(timeout=self.timeout)
                        ftps.connect(printer_ip, 990)
                        ftps.login(username, password)
                        ftps.cwd("/cache")
                        file_content = ftps.download_file(downloaded_file)
                    else:
                        raise
                except Exception as fb_dl_exc:
                    logger.error(f"[GCODE FTPS] ftplib fallback download failed: {fb_dl_exc}", exc_info=True)
                    try:
                        ftps.quit()
                    except Exception:
                        pass
                    return None

            # Prüfe ob .3mf Datei (ZIP-Archiv mit eingebettetem G-Code)
            try:
                if downloaded_file.lower().endswith('.3mf'):
                    weight = self._extract_weight_from_3mf(file_content, downloaded_file)
                else:
                    gcode_text = file_content.decode('utf-8', errors='ignore')
                    weight = self._extract_weight_from_gcode(gcode_text)
            except Exception as parse_exc:
                logger.error(f"[GCODE FTPS] Error extracting weight: {parse_exc}", exc_info=True)
                ftps.quit()
                return None

            ftps.quit()

            if weight:
                logger.info(f"[GCODE FTPS] OK Downloaded weight={weight:.2f}g from {downloaded_file}")
                return weight
            else:
                logger.warning(f"[GCODE FTPS] No weight found in G-Code file")
                return None

        except Exception as e:
            logger.error(f"[GCODE FTPS] Error downloading G-Code for task_id={task_id}: {e}", exc_info=True)
            return None
        finally:
            if ftps:
                try:
                    ftps.quit()
                except Exception as quit_exc:
                    logger.debug(f"[GCODE FTPS] Error during FTPS quit: {quit_exc}")

    def download_gcode_metrics(
        self,
        printer_ip: str,
        api_key: str,
        task_id: str,
        gcode_filename: Optional[str] = None
    ) -> dict:
        """
        Laedt G-Code/3MF und extrahiert Gewicht + Laenge.

        Returns:
            {"weight_g": float|None, "length_mm": float|None}
        """
        metrics: Dict[str, Optional[float]] = {"weight_g": None, "length_mm": None}
        ftps = None
        try:
            username = "bblp"
            password = api_key

            # Versuche SimpleFTPS, bei Fehler FTPLibFTPS als Fallback
            ftps = SimpleFTPS(timeout=self.timeout)
            try:
                ftps.connect(printer_ip, 990)
                ftps.login(username, password)
                ftps.cwd("/cache")
            except Exception as _conn_e:
                logger.warning(f"[METRICS FTPS] SimpleFTPS fehlgeschlagen, versuche FTPLibFTPS: {_conn_e}")
                try:
                    ftps.quit()
                except Exception:
                    pass
                ftps = FTPLibFTPS(timeout=self.timeout)
                ftps.connect(printer_ip, 990)
                ftps.login(username, password)
                ftps.cwd("/cache")
                logger.info(f"[METRICS FTPS] FTPLibFTPS Fallback OK fuer {printer_ip}")

            file_list_simple = ftps.list_dir(with_metadata=False)
            file_list_meta = ftps.list_dir(with_metadata=True)

            downloaded_file = None
            if gcode_filename:
                filename_base = gcode_filename.replace(".gcode", "").replace(".3mf", "")
                candidates = [gcode_filename, f"{filename_base}.gcode", f"{filename_base}.3mf"]
                for candidate in candidates:
                    if candidate in file_list_simple:
                        downloaded_file = candidate
                        break

            if not downloaded_file:
                gcode_files = [
                    f for f in file_list_meta
                    if f["name"].lower().endswith(".gcode") or f["name"].lower().endswith(".3mf")
                ]
                if gcode_files:
                    gcode_files_sorted = sorted(
                        gcode_files,
                        key=lambda x: x.get("mtime_str", ""),
                        reverse=True
                    )
                    downloaded_file = gcode_files_sorted[0]["name"]

            if not downloaded_file:
                try:
                    ftps.quit()
                except Exception:
                    pass
                return metrics

            file_content = ftps.download_file(downloaded_file)
            if downloaded_file.lower().endswith('.3mf'):
                weight, length = self._extract_metrics_from_3mf(file_content, downloaded_file)
            else:
                gcode_text = file_content.decode('utf-8', errors='ignore')
                weight, length = self._extract_metrics_from_gcode(gcode_text)

            metrics["weight_g"] = weight
            metrics["length_mm"] = length
            return metrics
        except Exception:
            return metrics
        finally:
            if ftps:
                try:
                    ftps.quit()
                except Exception:
                    pass

    def _find_3mf_by_title(
        self,
        ftps,
        target_filename: str,
        file_list_meta: list
    ) -> Optional[str]:
        """
        Findet .3mf Datei via Title-Matching (löst Problem mit unterschiedlichen Dateinamen)

        Strategie:
        1. Scanne alle .3mf Dateien im Cache
        2. Extrahiere Title aus jeder .3mf
        3. Vergleiche Title mit target_filename (normalisiert)
        4. Gebe beste Übereinstimmung zurück

        Args:
            ftps: FTP-Verbindung
            target_filename: Gesuchter Dateiname (z.B. "Heart_of_Dragon.gcode.3mf")
            file_list_meta: Liste aller Dateien im Cache

        Returns:
            Dateiname der besten Übereinstimmung oder None
        """
        try:
            # Normalisiere Ziel-Dateiname (entferne Erweiterungen, Leerzeichen, etc.)
            target_normalized = (
                target_filename.lower()
                .replace(".gcode", "")
                .replace(".3mf", "")
                .replace(" ", "")
                .replace("_", "")
                .replace("-", "")
            )

            logger.debug(f"[3MF TITLE MATCH] Searching for: '{target_filename}' (normalized: '{target_normalized}')")

            # Sammle alle .3mf Kandidaten
            three_mf_files = [
                f["name"] for f in file_list_meta
                if f["name"].lower().endswith(".3mf")
            ]

            if not three_mf_files:
                logger.debug("[3MF TITLE MATCH] No .3mf files found in cache")
                return None

            logger.debug(f"[3MF TITLE MATCH] Found {len(three_mf_files)} .3mf files to scan")

            best_match = None
            best_score = 0

            # Scanne jede .3mf Datei und extrahiere Title
            for filename in three_mf_files[:10]:  # Limit 10 Dateien (Performance)
                try:
                    # Download Datei temporär
                    file_content = ftps.download_file(filename)

                    # Speichere temporär
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.3mf') as tmp:
                        tmp.write(file_content)
                        tmp_path = tmp.name

                    try:
                        # Extrahiere Title
                        from app.utils.three_mf import extract_3mf_metadata
                        metadata = extract_3mf_metadata(tmp_path)
                        title = metadata.get('title', '')

                        if not title:
                            logger.debug(f"[3MF TITLE MATCH] {filename}: No title found")
                            continue

                        # Normalisiere Title
                        title_normalized = (
                            title.lower()
                            .replace(" ", "")
                            .replace("_", "")
                            .replace("-", "")
                        )

                        # Berechne Übereinstimmung (Prozent-basiert für Konfidenz)
                        # Score: 0-100 (Prozent Übereinstimmung)
                        score_raw = 0
                        if title_normalized in target_normalized or target_normalized in title_normalized:
                            # Vollständige Substring-Übereinstimmung
                            score_raw = min(len(title_normalized), len(target_normalized))
                        else:
                            # Partial Match: Zähle gemeinsame Zeichen von Anfang an
                            for i in range(min(len(title_normalized), len(target_normalized))):
                                if title_normalized[i] == target_normalized[i]:
                                    score_raw += 1
                                else:
                                    break

                        # Konvertiere zu Prozent (0-100)
                        max_len = max(len(title_normalized), len(target_normalized))
                        score_percent = int((score_raw / max_len * 100)) if max_len > 0 else 0

                        logger.debug(
                            f"[3MF TITLE MATCH] {filename}: title='{title}' "
                            f"(normalized: '{title_normalized}'), score={score_percent}%"
                        )

                        if score_percent > best_score:
                            best_score = score_percent
                            best_match = filename

                    finally:
                        # Lösche temporäre Datei
                        try:
                            Path(tmp_path).unlink()
                        except:
                            pass

                except Exception as e:
                    logger.debug(f"[3MF TITLE MATCH] Error scanning {filename}: {e}")
                    continue

            # Konfidenz-basierte Entscheidung
            # >= 60% = hohe Konfidenz, automatisch verwenden
            # < 60% = niedrige Konfidenz, USER MUSS BESTÄTIGEN
            if best_match and best_score >= 60:
                logger.info(
                    f"[3MF TITLE MATCH] ✓ High confidence match: '{best_match}' (score={best_score}%)"
                )
                return best_match
            elif best_match and best_score >= 30:
                logger.warning(
                    f"[3MF TITLE MATCH] ⚠ Low confidence match found: '{best_match}' (score={best_score}%) "
                    f"- BELOW 60% THRESHOLD - User must manually confirm file selection!"
                )
                logger.warning(
                    f"[3MF TITLE MATCH] User Action Required: "
                    f"Please manually download file '{best_match}' or select correct file from FTP cache."
                )
                # TODO: Implementiere File-Selection-Dialog im Frontend
                # Für jetzt: Fallback zu newest file
                return None
            else:
                logger.debug(
                    f"[3MF TITLE MATCH] No good match found (best_score={best_score}%)"
                )
                return None

        except Exception as e:
            logger.error(f"[3MF TITLE MATCH] Error during title matching: {e}", exc_info=True)
            return None

    def _extract_weight_from_3mf(self, file_content: bytes, filename: str) -> Optional[float]:
        """
        Extrahiert Filament-Gewicht aus .3mf Datei (ZIP mit eingebettetem G-Code)

        .3mf Dateien enthalten:
        - 3D/3dmodel.model mit Title metadata
        - Metadata/plate_*.gcode mit Slicer-Daten

        Args:
            file_content: Binäre Datei-Inhalte der .3mf Datei
            filename: Dateiname für Logging

        Returns:
            Filament-Gewicht in Gramm oder None
        """
        try:
            # Speichere temporär auf Disk (ZIP braucht echte Datei)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.3mf') as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name

            try:
                # Extrahiere Metadaten mit unserem 3MF Parser
                from app.utils.three_mf import extract_3mf_metadata

                metadata = extract_3mf_metadata(tmp_path)

                # Verwende total_filament_weight_g vom Slicer (präzisester Wert!)
                weight = metadata.get('total_filament_weight_g')

                if weight:
                    logger.info(
                        f"[3MF] Extracted from {filename}: "
                        f"weight={weight}g, length={metadata.get('total_filament_length_mm')}mm, "
                        f"title='{metadata.get('title')}'"
                    )
                    return weight
                else:
                    logger.warning(f"[3MF] No weight found in {filename}")
                    return None

            finally:
                # Lösche temporäre Datei
                try:
                    Path(tmp_path).unlink()
                except:
                    pass

        except Exception as e:
            logger.error(
                f"[3MF] Error extracting weight from {filename}: {e}",
                exc_info=True
            )
            return None

    def _extract_metrics_from_3mf(self, file_content: bytes, filename: str) -> Tuple[Optional[float], Optional[float]]:
        """Extrahiert Gewicht (g) und Laenge (mm) aus 3MF."""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.3mf') as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name
            try:
                from app.utils.three_mf import extract_3mf_metadata
                metadata = extract_3mf_metadata(tmp_path)
                weight = metadata.get('total_filament_weight_g')
                length = metadata.get('total_filament_length_mm')
                weight_f = float(weight) if weight is not None else None
                length_f = float(length) if length is not None else None
                return weight_f, length_f
            finally:
                try:
                    Path(tmp_path).unlink()
                except Exception:
                    pass
        except Exception:
            return None, None

    def _extract_weight_from_gcode(self, gcode_content: str) -> Optional[float]:
        """
        Extrahiert Filament-Gewicht aus G-Code Kommentaren

        Sucht nach Patterns wie:
        - ; filament used [g] = 15.80
        - ; total filament weight [g] = 1.11
        - ; filament_weight = 15.80
        - ; total_weight_g = 15.80
        """
        try:
            # Multiple Muster für verschiedene G-Code Formate
            patterns = [
                r"; filament used \[g\] = ([\d.]+)",  # Bambu Lab Standard
                r"; total filament weight \[g\] : ([\d.]+)",  # A1 Mini Format
                r"; filament_weight = ([\d.]+)",
                r"; total_weight_g = ([\d.]+)",
                r"; weight_used = ([\d.]+)",
            ]

            for pattern in patterns:
                match = re.search(pattern, gcode_content, re.IGNORECASE)
                if match:
                    try:
                        weight = float(match.group(1))
                        logger.debug(
                            f"[GCODE PARSE] Found weight={weight}g "
                            f"using pattern: {pattern}"
                        )
                        return weight
                    except (ValueError, IndexError):
                        continue

            logger.debug(
                "[GCODE PARSE] No weight comment found in G-Code"
            )
            return None

        except Exception as e:
            logger.error(
                f"[GCODE PARSE] Error parsing G-Code: {e}",
                exc_info=True
            )
            return None

    def _extract_weight_list_from_gcode(self, gcode_content: str) -> Optional[List[float]]:
        """
        Extrahiert per-Filament Gewichte aus G-Code Kommentaren (Multi-Color Drucke).

        Bambu Lab Format (Komma-getrennt, ein Wert pro Filament-Kanal):
            ; filament used [g] = 4.56, 21.30, 8.90

        Index 0 = AMS Slot 0 / Filament 1
        Index 1 = AMS Slot 1 / Filament 2
        usw.

        Returns:
            Liste mit Gewichten pro Filament-Kanal, oder None wenn nur ein Wert
            vorhanden ist (Single-Color) oder das Pattern nicht gefunden wurde.
        """
        try:
            # Bambu Studio schreibt: ; filament used [g] = 4.56, 21.30, 8.90
            pattern = r"; filament used \[g\] = ([\d.,\s]+)"
            match = re.search(pattern, gcode_content, re.IGNORECASE)
            if not match:
                return None

            values_str = match.group(1).strip().rstrip(',')
            if ',' not in values_str:
                # Nur ein Wert -> Single-Color, kein per-Filament Split noetig
                return None

            weights: List[float] = []
            for v in values_str.split(','):
                v = v.strip()
                if v:
                    try:
                        weights.append(float(v))
                    except ValueError:
                        weights.append(0.0)

            if len(weights) < 2:
                return None

            logger.debug(
                f"[GCODE PARSE] Per-Filament Gewichte gefunden: {weights} "
                f"(total={sum(weights):.2f}g)"
            )
            return weights

        except Exception as e:
            logger.error(
                f"[GCODE PARSE] Fehler beim Parsen der per-Filament Gewichte: {e}",
                exc_info=True,
            )
            return None

    def download_gcode_details(
        self,
        printer_ip: str,
        api_key: str,
        task_id: str,
        gcode_filename: Optional[str] = None,
    ) -> Dict:
        """
        Laedt G-Code vom Drucker und extrahiert sowohl das Gesamt-Gewicht
        als auch die per-Filament Gewichte fuer Multi-Color Tracking.

        Returns dict mit:
            {
                "total_weight": float | None,        # Gesamtgewicht
                "per_filament": [float] | None,      # Gewicht pro Slot/Filament-Index
                "filename": str | None,              # Heruntergeladene Datei
            }
        """
        # Starte mit dem normalen Download (nutzt bestehende FTP-Logik)
        total_weight = self.download_gcode_weight(
            printer_ip=printer_ip,
            api_key=api_key,
            task_id=task_id,
            gcode_filename=gcode_filename,
        )

        # Zweiter Pass: per-Filament Gewichte aus dem bereits gecachten/
        # heruntergeladenen G-Code-Text extrahieren.
        # Da download_gcode_weight() die Datei intern verarbeitet, muessen wir
        # hier einen zweiten leichtgewichtigen Download-Versuch starten.
        # Optimierung: Direkt den gcode-Text erneut holen (kein Doppel-FTP-Login
        # noetig, weil die Datei auf dem Drucker gecacht ist und klein ist).
        per_filament: Optional[List[float]] = None
        try:
            raw_content = self._download_raw_gcode_content(
                printer_ip=printer_ip,
                api_key=api_key,
                gcode_filename=gcode_filename,
            )
            if raw_content:
                if isinstance(raw_content, bytes):
                    # Pruefen ob 3MF (ZIP)
                    if raw_content[:4] == b'PK\x03\x04':
                        # 3MF: per-Filament Daten aus eingebettetem G-Code
                        import zipfile, io as _io
                        try:
                            with zipfile.ZipFile(_io.BytesIO(raw_content)) as zf:
                                for name in zf.namelist():
                                    if name.lower().endswith('.gcode'):
                                        gcode_text = zf.read(name).decode('utf-8', errors='ignore')
                                        per_filament = self._extract_weight_list_from_gcode(gcode_text)
                                        break
                        except Exception:
                            pass
                    else:
                        gcode_text = raw_content.decode('utf-8', errors='ignore')
                        per_filament = self._extract_weight_list_from_gcode(gcode_text)
        except Exception as e:
            logger.debug(f"[GCODE DETAILS] Per-Filament Extraktion fehlgeschlagen: {e}")

        if per_filament:
            logger.info(
                f"[GCODE DETAILS] task_id={task_id} total={total_weight}g "
                f"per_filament={per_filament}"
            )

        return {
            "total_weight": total_weight,
            "per_filament": per_filament,
        }

    def _download_raw_gcode_content(
        self,
        printer_ip: str,
        api_key: str,
        gcode_filename: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Hilfsmethode: Laedt den rohen G-Code-Datei-Inhalt per FTPS.
        Vereinfachte Version von download_gcode_weight() ohne Parsing.
        """
        ftps = None
        try:
            username = "bblp"
            password = api_key
            ftps = SimpleFTPS(timeout=self.timeout)
            ftps.connect(printer_ip, 990)
            ftps.login(username, password)
            ftps.cwd("/cache")

            file_list = ftps.list_dir(with_metadata=False)

            target_file: Optional[str] = None
            if gcode_filename:
                base = gcode_filename.replace(".gcode", "").replace(".3mf", "")
                for candidate in [gcode_filename, f"{base}.gcode", f"{base}.3mf"]:
                    if candidate in file_list:
                        target_file = candidate
                        break

            if not target_file:
                ftps.quit()
                return None

            content = ftps.download_file(target_file)
            ftps.quit()
            return content

        except Exception as e:
            logger.debug(f"[GCODE RAW] Download fehlgeschlagen: {e}")
            if ftps:
                try:
                    ftps.quit()
                except Exception:
                    pass
            return None

    def _extract_metrics_from_gcode(self, gcode_content: str) -> Tuple[Optional[float], Optional[float]]:
        """Extrahiert Gewicht (g) und Laenge (mm) aus G-Code Kommentaren."""
        weight: Optional[float] = None
        length_mm: Optional[float] = None
        try:
            weight_patterns = [
                r"; filament used \[g\] = ([\d.]+)",
                r"; total filament weight \[g\] : ([\d.]+)",
                r"; filament_weight = ([\d.]+)",
                r"; total_weight_g = ([\d.]+)",
                r"; weight_used = ([\d.]+)",
            ]
            for pattern in weight_patterns:
                match = re.search(pattern, gcode_content, re.IGNORECASE)
                if match:
                    try:
                        weight = float(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue

            length_mm_patterns = [
                r"; filament used \[mm\] = ([\d.]+)",
                r"; total filament used \[mm\] = ([\d.]+)",
                r"; total_filament_length_mm = ([\d.]+)",
                r"; filament_length_mm = ([\d.]+)",
            ]
            for pattern in length_mm_patterns:
                match = re.search(pattern, gcode_content, re.IGNORECASE)
                if match:
                    try:
                        length_mm = float(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue

            if length_mm is None:
                length_m_patterns = [
                    r"; filament used \[m\] = ([\d.]+)",
                    r"; filament_length_m = ([\d.]+)",
                ]
                for pattern in length_m_patterns:
                    match = re.search(pattern, gcode_content, re.IGNORECASE)
                    if match:
                        try:
                            length_mm = float(match.group(1)) * 1000.0
                            break
                        except (ValueError, IndexError):
                            continue
        except Exception:
            return weight, length_mm
        return weight, length_mm

    def verify_connection(
        self,
        printer_ip: str,
        api_key: str
    ) -> Tuple[bool, str]:
        """
        Testet FTPS-Verbindung zum Drucker

        Returns:
            (success: bool, message: str)
        """
        ftps = None
        try:
            username = "bblp"
            password = api_key

            ftps = SimpleFTPS(timeout=self.timeout)
            ftps.connect(printer_ip, 990)
            ftps.login(username, password)
            ftps.cwd("/cache")
            ftps.quit()

            return True, f"OK FTPS connection successful to {printer_ip}"

        except socket.timeout:
            return False, "ERROR FTPS connection timeout"
        except Exception as e:
            return False, f"ERROR FTPS connection failed: {str(e)}"
        finally:
            if ftps:
                try:
                    ftps.quit()
                except:
                    pass


# Singleton instance
_gcode_ftp_service: Optional[GcodeFTPService] = None


def get_gcode_ftp_service() -> GcodeFTPService:
    """Get or create GcodeFTPService singleton"""
    global _gcode_ftp_service
    if _gcode_ftp_service is None:
        _gcode_ftp_service = GcodeFTPService()
    return _gcode_ftp_service
