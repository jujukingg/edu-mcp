"""Local secure web UI (127.0.0.1) for configuring Pronote via QR Code or credentials."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse
import uuid as uuid_lib
import webbrowser

from dotenv import dotenv_values
from pronote_mcp.config import PronoteSettings, _ENV_PATH, save_env_config

_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
_LOGO_PATH = _ASSETS_DIR / "logo.png"


class HeadlessEnvironmentError(RuntimeError):
    """Raised when a local browser cannot be opened for interactive setup."""


def validate_setup_inputs(
    url: str,
    username: str,
    password: str,
    pin: str = "",
) -> Optional[str]:
    """Validate classic credential form fields before attempting a live connection."""
    clean_url = url.strip()
    if not clean_url:
        return "L'URL Pronote est obligatoire."
    parsed = urlparse(clean_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "URL invalide (elle doit commencer par https:// ou http://)."
    if not username.strip():
        return "L'identifiant est obligatoire."
    if not password:
        return "Le mot de passe est obligatoire."
    clean_pin = pin.strip()
    if clean_pin and not re.fullmatch(r"\d{4}", clean_pin):
        return "Le code PIN 2FA doit contenir exactement 4 chiffres."
    return None


def validate_qr_inputs(qr_json_text: str, qr_pin: str, account_pin: str = "") -> Optional[str]:
    """Validate QR code JSON payload and 4-digit confirmation PIN."""
    raw = qr_json_text.strip()
    if not raw:
        return "Le contenu JSON du QR Code Pronote est obligatoire."
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "Le texte saisi n'est pas un JSON valide."
    if not isinstance(data, dict) or not all(k in data for k in ("login", "jeton", "url")):
        return "Le JSON du QR Code doit contenir les clés 'login', 'jeton' et 'url'."
    if not re.fullmatch(r"\d{4}", qr_pin.strip()):
        return "Le code PIN du QR Code doit contenir exactement 4 chiffres."
    clean_2fa = account_pin.strip()
    if clean_2fa and not re.fullmatch(r"\d{4}", clean_2fa):
        return "Le code PIN 2FA doit contenir exactement 4 chiffres."
    return None


def verify_and_save_credentials(
    payload: Dict[str, str],
    env_path: Optional[Path] = None,
    connector_factory: Optional[Callable[[PronoteSettings], Any]] = None,
) -> PronoteSettings:
    """Test Pronote authentication in memory, persist session cache, and save .env on success."""
    from pronote_mcp.client import PronoteSessionManager

    candidate = PronoteSettings(_env_file=None, **payload)
    manager = connector_factory(candidate) if connector_factory else PronoteSessionManager(candidate)
    manager._connect_sync()

    target_path = save_env_config(payload, env_path=env_path)
    return PronoteSettings(_env_file=str(target_path))


def verify_and_save_qr_credentials(
    qr_json_text: str,
    qr_pin: str,
    account_type: str = "student",
    account_pin: str = "",
    device_name: str = "MCP Assistant",
    env_path: Optional[Path] = None,
    qr_login_fn: Optional[Callable[..., Any]] = None,
) -> PronoteSettings:
    """Authenticate via Pronote QR code JSON, cache session, and save token credentials to .env."""
    import pronotepy
    from pronote_mcp.client import PronoteSessionManager

    qr_data = json.loads(qr_json_text.strip())
    is_parent = account_type == "parent"
    client_cls = pronotepy.ParentClient if is_parent else pronotepy.Client
    login_fn = qr_login_fn or client_cls.qrcode_login

    stable_uuid = uuid_lib.uuid4().hex
    pin_2fa = account_pin.strip() or None
    client = login_fn(
        qr_code=qr_data,
        pin=qr_pin.strip(),
        uuid=stable_uuid,
        account_pin=pin_2fa,
        device_name=device_name.strip() or "MCP Assistant",
    )
    if not getattr(client, "logged_in", False):
        raise ConnectionError("Échec de l'authentification par QR Code Pronote.")

    creds = client.export_credentials() if hasattr(client, "export_credentials") else {}
    payload: Dict[str, str] = {
        "PRONOTE_URL": str(creds.get("url") or qr_data["url"]),
        "PRONOTE_USERNAME": str(creds.get("username") or getattr(client, "username", "")),
        "PRONOTE_TOKEN": str(creds.get("password") or getattr(client, "password", "")),
        "PRONOTE_UUID": str(creds.get("uuid") or stable_uuid),
        "PRONOTE_ACCOUNT_TYPE": "parent" if is_parent else "student",
        "PRONOTE_DEVICE_NAME": device_name.strip() or "MCP Assistant",
    }
    if pin_2fa:
        payload["PRONOTE_ACCOUNT_PIN"] = pin_2fa

    target_path = save_env_config(payload, env_path=env_path)
    saved = PronoteSettings(_env_file=str(target_path))
    PronoteSessionManager(saved)._save_cached_session(client)
    return saved


def _build_html_page(csrf_token: str, env_display_path: str, ent_choices: List[str], defaults: Dict[str, str]) -> str:
    """Render the self-contained local configuration page."""
    ent_options = "".join(f'<option value="{e}">{e}</option>' for e in sorted(ent_choices))
    default_url = defaults.get("PRONOTE_URL", "").replace('"', "&quot;")
    default_user = defaults.get("PRONOTE_USERNAME", "").replace('"', "&quot;")
    default_pin = defaults.get("PRONOTE_ACCOUNT_PIN", "").replace('"', "&quot;")
    default_device = (defaults.get("PRONOTE_DEVICE_NAME") or "MCP Assistant").replace('"', "&quot;")
    default_type = defaults.get("PRONOTE_ACCOUNT_TYPE", "student")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pronote MCP — Configuration locale sécurisée</title>
  <link rel="icon" type="image/png" href="/logo.png" />
  <style>
    :root {{
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #e2e8f0;
      --text: #0f172a;
      --muted: #475569;
      --accent: #059669;
      --accent-hover: #047857;
      --accent-soft: #ecfdf5;
      --danger: #dc2626;
      --danger-soft: #fef2f2;
      --info: #0284c7;
      --info-soft: #f0f9ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text);
      display: flex; justify-content: center; align-items: flex-start; min-height: 100vh;
    }}
    .container {{ width: 100%; max-width: 520px; }}
    .header {{ display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }}
    .header img {{ width: 52px; height: 52px; border-radius: 12px; }}
    .header h1 {{ margin: 0; font-size: 1.35rem; }}
    .badge {{
      display: inline-block; margin-top: 4px; padding: 3px 9px; border-radius: 999px;
      background: var(--accent-soft); color: var(--accent); font-size: 0.78rem; font-weight: 600;
    }}
    .card {{
      background: var(--card); border: 1px solid var(--border); border-radius: 14px;
      padding: 22px; box-shadow: 0 4px 20px rgba(15, 23, 42, 0.05);
    }}
    .trust-box {{
      background: var(--info-soft); border: 1px solid #bae6fd; color: #0c4a6e;
      border-radius: 10px; padding: 10px 12px; font-size: 0.84rem; line-height: 1.45; margin-bottom: 16px;
    }}
    .trust-box code {{ font-family: ui-monospace, Consolas, monospace; font-size: 0.79rem; word-break: break-all; }}
    .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }}
    .tab {{
      flex: 1; padding: 9px 10px; border: 1px solid var(--border); border-radius: 8px;
      background: #f1f5f9; color: var(--muted); font-weight: 600; font-size: 0.88rem; cursor: pointer;
    }}
    .tab.active {{ background: var(--accent-soft); color: var(--accent); border-color: #a7f3d0; }}
    .panel {{ display: none; }}
    .panel.active {{ display: block; }}
    .row {{ display: flex; gap: 10px; }}
    .field {{ margin-bottom: 12px; flex: 1; }}
    label {{ display: block; font-size: 0.84rem; font-weight: 600; margin-bottom: 5px; }}
    input, select, textarea {{
      width: 100%; padding: 9px 11px; border: 1px solid var(--border); border-radius: 8px;
      font-size: 0.92rem; font-family: inherit; background: #fff; color: var(--text);
    }}
    input:focus, select:focus, textarea:focus {{ outline: 2px solid #a7f3d0; border-color: var(--accent); }}
    textarea {{ min-height: 82px; font-family: ui-monospace, Consolas, monospace; font-size: 0.82rem; }}
    .actions {{ display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }}
    button.primary {{
      background: var(--accent); color: #fff; border: none; border-radius: 8px;
      padding: 10px 18px; font-weight: 600; font-size: 0.92rem; cursor: pointer;
    }}
    button.primary:hover {{ background: var(--accent-hover); }}
    button.primary:disabled {{ opacity: 0.6; cursor: wait; }}
    button.secondary {{
      background: #fff; color: var(--muted); border: 1px solid var(--border); border-radius: 8px;
      padding: 10px 14px; font-weight: 600; font-size: 0.92rem; cursor: pointer;
    }}
    .status {{ margin-top: 12px; padding: 10px 12px; border-radius: 8px; font-size: 0.86rem; display: none; }}
    .status.err {{ display: block; background: var(--danger-soft); color: var(--danger); border: 1px solid #fecaca; }}
    .status.ok {{ display: block; background: var(--accent-soft); color: var(--accent); border: 1px solid #a7f3d0; }}
    .status.info {{ display: block; background: var(--info-soft); color: var(--info); border: 1px solid #bae6fd; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <img src="/logo.png" alt="Pronote MCP" onerror="this.style.display='none'" />
      <div>
        <h1>Pronote MCP</h1>
        <span class="badge">127.0.0.1 • Serveur local uniquement</span>
      </div>
    </div>

    <div class="card">
      <div class="trust-box">
        <strong>Confidentialité :</strong> cette page tourne localement sur votre ordinateur. Aucune donnée n'est envoyée au chat IA ni à un serveur tiers.<br/>
        Fichier cible : <code>{env_display_path}</code>
      </div>

      <div class="tabs">
        <button type="button" class="tab active" onclick="switchTab('browser', this)">Navigateur officiel (SSO / ENT)</button>
        <button type="button" class="tab" onclick="switchTab('qr', this)">QR Code</button>
        <button type="button" class="tab" onclick="switchTab('classic', this)">Identifiants</button>
      </div>

      <div id="panel-browser" class="panel active">
        <div class="row">
          <div class="field">
            <label>Type de compte</label>
            <select id="br_type">
              <option value="student" {"selected" if default_type == "student" else ""}>Élève (student)</option>
              <option value="parent" {"selected" if default_type == "parent" else ""}>Parent (parent)</option>
            </select>
          </div>
          <div class="field">
            <label>Navigateur</label>
            <select id="br_browser">
              <option value="auto">Auto (Edge / Chrome)</option>
              <option value="brave">Brave</option>
              <option value="msedge">Microsoft Edge</option>
              <option value="chrome">Google Chrome</option>
              <option value="firefox">Firefox</option>
            </select>
          </div>
          <div class="field">
            <label>PIN 2FA (auto-détecté si saisi)</label>
            <input id="br_2fa" type="password" inputmode="numeric" maxlength="4" value="{default_pin}" placeholder="Auto" />
          </div>
        </div>
        <div class="field">
          <label>URL de votre Pronote ou ENT *</label>
          <input id="br_url" type="url" value="{default_url}" placeholder="https://exemple.index-education.net/pronote/eleve.html" />
        </div>
        <p style="margin: 4px 0 0; font-size: 0.82rem; color: var(--muted); line-height: 1.4;">
          Ouvre votre navigateur avec un profil dédié persistant (mots de passe mémorisés). Connectez-vous normalement (ENT, EduConnect, 2FA…) : tout est récupéré automatiquement.
        </p>
      </div>

      <div id="panel-qr" class="panel">
        <div class="field">
          <label>Type de compte</label>
          <select id="qr_type">
            <option value="student" {"selected" if default_type == "student" else ""}>Élève (student)</option>
            <option value="parent" {"selected" if default_type == "parent" else ""}>Parent (parent)</option>
          </select>
        </div>
        <div class="field">
          <label>JSON du QR Code Pronote *</label>
          <textarea id="qr_json" placeholder='{{"jeton": "...", "login": "...", "url": "https://.../eleve.html"}}'></textarea>
        </div>
        <div class="row">
          <div class="field">
            <label>Code PIN du QR Code *</label>
            <input id="qr_pin" type="password" inputmode="numeric" maxlength="4" placeholder="4 chiffres" />
          </div>
          <div class="field">
            <label>PIN 2FA (optionnel)</label>
            <input id="qr_2fa" type="password" inputmode="numeric" maxlength="4" value="{default_pin}" placeholder="0000" />
          </div>
        </div>
      </div>

      <div id="panel-classic" class="panel">
        <div class="row">
          <div class="field">
            <label>Type de compte</label>
            <select id="cl_type">
              <option value="student" {"selected" if default_type == "student" else ""}>Élève (student)</option>
              <option value="parent" {"selected" if default_type == "parent" else ""}>Parent (parent)</option>
            </select>
          </div>
          <div class="field">
            <label>ENT (optionnel)</label>
            <select id="cl_ent">
              <option value="">Connexion directe (sans ENT)</option>
              {ent_options}
            </select>
          </div>
        </div>
        <div class="field">
          <label>URL Pronote *</label>
          <input id="cl_url" type="url" value="{default_url}" placeholder="https://exemple.index-education.net/pronote/eleve.html" />
        </div>
        <div class="field">
          <label>Identifiant *</label>
          <input id="cl_user" type="text" value="{default_user}" placeholder="prenom.nom" />
        </div>
        <div class="row">
          <div class="field">
            <label>Mot de passe *</label>
            <input id="cl_pass" type="password" placeholder="Votre mot de passe" />
          </div>
          <div class="field">
            <label>PIN 2FA (optionnel)</label>
            <input id="cl_pin" type="password" inputmode="numeric" maxlength="4" value="{default_pin}" placeholder="0000" />
          </div>
        </div>
      </div>

      <div class="field">
        <label>Nom de l'appareil</label>
        <input id="device_name" type="text" value="{default_device}" placeholder="MCP Assistant" />
      </div>

      <div id="status" class="status"></div>

      <div class="actions">
        <button type="button" class="secondary" onclick="cancelSetup()">Annuler</button>
        <button type="button" class="primary" id="submitBtn" onclick="submitSetup()">Tester et enregistrer</button>
      </div>
    </div>
  </div>

  <script>
    let activeMode = "browser";
    const csrfToken = "{csrf_token}";

    function switchTab(mode, btn) {{
      activeMode = mode;
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("panel-" + mode).classList.add("active");
      setStatus("", "");
    }}

    function setStatus(cls, msg) {{
      const el = document.getElementById("status");
      el.className = "status" + (cls ? " " + cls : "");
      el.textContent = msg;
    }}

    async function submitSetup() {{
      const btn = document.getElementById("submitBtn");
      btn.disabled = true;
      setStatus("info", "Test de connexion à Pronote en cours...");

      const body = activeMode === "browser" ? {{
        mode: "browser",
        csrf: csrfToken,
        account_type: document.getElementById("br_type").value,
        browser_choice: document.getElementById("br_browser").value,
        url: document.getElementById("br_url").value,
        account_pin: document.getElementById("br_2fa").value,
        device_name: document.getElementById("device_name").value
      }} : activeMode === "qr" ? {{
        mode: "qr",
        csrf: csrfToken,
        account_type: document.getElementById("qr_type").value,
        qr_json: document.getElementById("qr_json").value,
        qr_pin: document.getElementById("qr_pin").value,
        account_pin: document.getElementById("qr_2fa").value,
        device_name: document.getElementById("device_name").value
      }} : {{
        mode: "classic",
        csrf: csrfToken,
        account_type: document.getElementById("cl_type").value,
        ent: document.getElementById("cl_ent").value,
        url: document.getElementById("cl_url").value,
        username: document.getElementById("cl_user").value,
        password: document.getElementById("cl_pass").value,
        pin: document.getElementById("cl_pin").value,
        device_name: document.getElementById("device_name").value
      }};

      try {{
        const res = await fetch("/api/verify", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify(body)
        }});
        const data = await res.json();
        if (data.ok) {{
          setStatus("ok", "Connexion réussie et session enregistrée ! Vous pouvez fermer cet onglet.");
          return;
        }}
        setStatus("err", data.error || "Erreur inconnue.");
      }} catch (e) {{
        setStatus("err", "Impossible de joindre le serveur local : " + e);
      }}
      btn.disabled = false;
    }}

    async function cancelSetup() {{
      await fetch("/api/cancel", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{csrf: csrfToken}})
      }}).catch(() => {{}});
      setStatus("info", "Configuration annulée. Vous pouvez fermer cet onglet.");
    }}
  </script>
</body>
</html>"""


def _load_default_values(
    initial_values: Optional[Dict[str, str]],
    target_env: Path,
) -> Dict[str, str]:
    """Build form defaults from existing .env / environment variables and explicit overrides."""
    merged: Dict[str, str] = {}
    for candidate in (Path.cwd() / ".env", target_env):
        if candidate.is_file():
            for k, v in dotenv_values(candidate).items():
                if v:
                    merged[k] = v
    for key in ("PRONOTE_URL", "PRONOTE_USERNAME", "PRONOTE_ACCOUNT_PIN", "PRONOTE_ACCOUNT_TYPE", "PRONOTE_DEVICE_NAME"):
        if os.environ.get(key):
            merged[key] = os.environ[key]
    if initial_values:
        merged.update(initial_values)
    return merged


def open_setup_popup(
    env_path: Optional[Path] = None,
    ent_choices: Optional[List[str]] = None,
    initial_values: Optional[Dict[str, str]] = None,
    timeout_seconds: int = 300,
) -> Optional[PronoteSettings]:
    """Start an ephemeral localhost HTTP server, open it in the browser, and wait for setup."""
    csrf_token = secrets.token_urlsafe(24)
    done_event = threading.Event()
    result_box: Dict[str, Optional[PronoteSettings]] = {"settings": None}
    target_env = (env_path or _ENV_PATH).resolve()
    defaults = _load_default_values(initial_values, target_env)
    html_body = _build_html_page(
        csrf_token=csrf_token,
        env_display_path=str(target_env),
        ent_choices=ent_choices or [],
        defaults=defaults,
    ).encode("utf-8")

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, code: int, data: Dict[str, Any]) -> None:
            raw = json.dumps(data).encode("utf-8")
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                pass

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/logo.png" and _LOGO_PATH.exists():
                img = _LOGO_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(img)))
                self.end_headers()
                self.wfile.write(img)
                return

            qs = parse_qs(parsed.query)
            if parsed.path != "/" or qs.get("token", [""])[0] != csrf_token:
                self.send_response(403)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(html_body)))
            self.end_headers()
            self.wfile.write(html_body)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 65536))
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json(400, {"ok": False, "error": "Requête JSON invalide."})
                return

            if body.get("csrf") != csrf_token:
                self._send_json(403, {"ok": False, "error": "Jeton de session invalide."})
                return

            if self.path == "/api/cancel":
                self._send_json(200, {"ok": True})
                done_event.set()
                return

            if self.path != "/api/verify":
                self._send_json(404, {"ok": False, "error": "Route inconnue."})
                return

            mode = body.get("mode")
            try:
                if mode == "browser":
                    from pronote_mcp.browser_auth import authenticate_via_browser

                    settings = authenticate_via_browser(
                        target_url=body.get("url", ""),
                        account_type=body.get("account_type", "student"),
                        account_pin=body.get("account_pin", ""),
                        device_name=body.get("device_name", "MCP Assistant"),
                        env_path=env_path,
                        browser_choice=body.get("browser_choice", "auto"),
                    )
                elif mode == "qr":
                    err = validate_qr_inputs(body.get("qr_json", ""), body.get("qr_pin", ""), body.get("account_pin", ""))
                    if err:
                        self._send_json(400, {"ok": False, "error": err})
                        return
                    settings = verify_and_save_qr_credentials(
                        qr_json_text=body.get("qr_json", ""),
                        qr_pin=body.get("qr_pin", ""),
                        account_type=body.get("account_type", "student"),
                        account_pin=body.get("account_pin", ""),
                        device_name=body.get("device_name", "MCP Assistant"),
                        env_path=env_path,
                    )
                else:
                    err = validate_setup_inputs(
                        body.get("url", ""),
                        body.get("username", ""),
                        body.get("password", ""),
                        body.get("pin", ""),
                    )
                    if err:
                        self._send_json(400, {"ok": False, "error": err})
                        return
                    payload: Dict[str, str] = {
                        "PRONOTE_URL": body["url"].strip(),
                        "PRONOTE_ACCOUNT_TYPE": body.get("account_type", "student") or "student",
                        "PRONOTE_ENT": body.get("ent", "").strip(),
                        "PRONOTE_USERNAME": body["username"].strip(),
                        "PRONOTE_PASSWORD": body["password"],
                        "PRONOTE_DEVICE_NAME": (body.get("device_name") or "MCP Assistant").strip(),
                    }
                    if body.get("pin", "").strip():
                        payload["PRONOTE_ACCOUNT_PIN"] = body["pin"].strip()
                    settings = verify_and_save_credentials(payload, env_path=env_path)

                result_box["settings"] = settings
                self._send_json(200, {"ok": True})
                done_event.set()
            except Exception as exc:
                try:
                    from pronote_mcp.browser_auth import get_sso_logger

                    get_sso_logger((env_path.parent / "sso_debug.log") if env_path else None).exception(
                        "Erreur lors de /api/verify (mode=%s): %s", mode, exc
                    )
                except Exception:
                    pass
                self._send_json(400, {"ok": False, "error": f"Échec de connexion : {exc}"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/?token={csrf_token}"
    print(f"Pronote MCP setup UI: {url}", flush=True)

    srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
    srv_thread.start()
    try:
        opened = webbrowser.open(url)
        if not opened:
            raise HeadlessEnvironmentError(
                "Impossible d'ouvrir le navigateur local. "
                "Configurez le fichier .env manuellement sans partager vos identifiants dans le chat."
            )
        done_event.wait(timeout=timeout_seconds)
    finally:
        server.shutdown()
        server.server_close()

    return result_box["settings"]
