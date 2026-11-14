"""Browser-based official Pronote/ENT authentication using system Edge/Chrome via Playwright."""

import base64
import json
import logging
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import threading
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse
import uuid as uuid_lib

import requests
from pronote_mcp.config import PronoteSettings, get_app_data_dir, save_env_config

_SSO_LOG_FILE = get_app_data_dir() / "sso_debug.log"


def get_sso_logger(log_path: Optional[Path] = None) -> logging.Logger:
    """Return a logger writing detailed SSO diagnostics to stderr and sso_debug.log."""
    logger = logging.getLogger("pronote_mcp.sso")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    target_file = (log_path or (get_app_data_dir() / "sso_debug.log")).resolve()
    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers):
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.INFO)
        sh.setFormatter(logging.Formatter("[SSO %(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S"))
        logger.addHandler(sh)

    if not any(isinstance(h, logging.FileHandler) and Path(h.baseFilename).resolve() == target_file for h in logger.handlers):
        try:
            fh = logging.FileHandler(target_file, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(fh)
        except OSError:
            pass
    return logger


def _launch_browser_context(
    p: Any,
    logger: Optional[logging.Logger] = None,
) -> tuple[Any, Any]:
    """Launch system Edge/Chrome cleanly via Playwright (no browser picker needed).

    Returns (browser_or_none, context).
    """
    log = logger or get_sso_logger()
    last_err: Optional[Exception] = None
    for channel in ("msedge", "chrome", None):
        label = channel or "chromium"
        try:
            kwargs: Dict[str, Any] = {"headless": False}
            if channel:
                kwargs["channel"] = channel
            log.info("Tentative lancement navigateur natif (%s)...", label)
            browser = p.chromium.launch(**kwargs)
            context = browser.new_context()
            log.info("Navigateur lancé avec succès (%s).", label)
            return browser, context
        except Exception as exc:
            log.warning("Échec lancement %s: %s", label, exc)
            last_err = exc

    try:
        log.info("Aucun navigateur système détecté, installation automatique de Chromium via Playwright...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        log.info("Navigateur Chromium téléchargé et lancé avec succès.")
        return browser, context
    except Exception as install_exc:
        last_err = install_exc

    raise RuntimeError(
        "Impossible de lancer Edge, Chrome ou Chromium via Playwright. "
        "Exécutez `playwright install chromium` ou vérifiez qu'un navigateur est installé."
    ) from last_err


def cookies_to_jar(cookies: list[dict[str, Any]]) -> requests.cookies.RequestsCookieJar:
    """Convert Playwright cookie dicts into a requests CookieJar."""
    jar = requests.cookies.RequestsCookieJar()
    for c in cookies:
        jar.set(
            c["name"],
            c["value"],
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
        )
    return jar


def _inspect_pronote_page(page: Any) -> Dict[str, Any]:
    """Inspect a browser page DOM to determine Pronote authentication state and log diagnostics."""
    url = page.url or ""
    url_lower = url.lower()
    if not any(tag in url_lower for tag in ("eleve.html", "parent.html")):
        return {"url": url, "is_pronote_space": False, "authenticated": False}
    try:
        info = page.evaluate(
            """() => {
                const isVisible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
                const pwd = document.querySelector('input[type="password"]');
                const pwdVisible = isVisible(pwd);

                const modalEls = Array.from(document.querySelectorAll(
                    '.Fenetre_Cadre, .fenetre_modale, [role="dialog"], [role="alertdialog"], [aria-modal="true"], [class*="Fenetre"], .voile_page'
                ));
                const visibleModals = modalEls.filter(isVisible).map(m => ({
                    tag: m.tagName,
                    id: m.id || '',
                    cls: (m.className && typeof m.className === 'string') ? m.className : '',
                    role: m.getAttribute('role') || '',
                    text: (m.innerText || '').trim().slice(0, 60).replace(/\\s+/g, ' ')
                }));

                const dashboardCount = document.querySelectorAll(
                    '.widget, .accueil-widget, .ObjetMenu_Contenu, .menu-principal'
                ).length;
                const title = document.title || '';
                const bodyLen = (document.body && document.body.innerText) ? document.body.innerText.trim().length : 0;
                const isLoginTitle = title.trim().toLowerCase().startsWith('connexion');
                const authenticated = !pwdVisible && visibleModals.length === 0 && !isLoginTitle && dashboardCount > 0 && bodyLen > 120;
                return {
                    title,
                    pwdVisible,
                    visibleModals,
                    dashboardCount,
                    bodyLen,
                    isLoginTitle,
                    authenticated
                };
            }"""
        )
        info["url"] = url
        info["is_pronote_space"] = True
        return info
    except Exception as exc:
        return {"url": url, "is_pronote_space": True, "authenticated": False, "eval_error": repr(exc)}


def _is_pronote_authenticated_page(page: Any) -> bool:
    """Check whether a browser page has reached a logged-in Pronote space (after any 2FA modal)."""
    return bool(_inspect_pronote_page(page).get("authenticated", False))


def _normalize_pronote_space_url(current_url: str, account_type: str) -> str:
    """Extract clean base Pronote space URL (eleve.html or parent.html)."""
    parsed = urlparse(current_url)
    path = parsed.path or f"/{'parent' if account_type == 'parent' else 'eleve'}.html"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _decode_qr_data_url(data_url: str) -> Dict[str, Any]:
    """Decode a base64 PNG data URL containing a Pronote QR code into its JSON dict."""
    import cv2
    import numpy as np

    if "base64," not in data_url:
        raise ValueError("Format d'image QR Code invalide (base64 manquant).")
    b64_part = data_url.split("base64,", 1)[1]
    raw_bytes = base64.b64decode(b64_part)
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Impossible de décoder l'image PNG du QR Code.")
    # Composite transparent PNGs onto white so dark modules aren't lost on black.
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3:4] / 255.0
        bgr = img[:, :, :3]
        img = (bgr * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.copyMakeBorder(img, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    if not decoded:
        raise ValueError("Impossible de lire le QR Code généré par Pronote.")
    return json.loads(decoded)


def _update_info_banner(page: Any, text: str) -> None:
    """Update the in-page Pronote MCP banner text so the user sees live progress."""
    try:
        page.evaluate(
            """(msg) => {
                const bar = document.getElementById('pronote-mcp-info-banner');
                if (bar) {
                    const span = bar.querySelector('span');
                    if (span) {
                        span.innerHTML = '<strong style="color:#34d399;">Pronote MCP</strong> : ' + msg;
                    }
                }
            }""",
            text,
        )
    except Exception:
        pass


def _extract_qr_via_browser_dom(page: Any, pin: str, logger: logging.Logger) -> Dict[str, Any]:
    """Automate Pronote's built-in 'QR code de l'application' modal in the already logged-in page."""
    logger.info("Extraction automatique du QR Code via l'interface Pronote ouverte...")
    _update_info_banner(page, "Connexion réussie ! Génération automatique du jeton en cours, ne fermez pas cette fenêtre…")

    logger.info("QR DOM [1/5] : recherche et clic sur le bouton QR code...")
    qr_btn = page.get_by_role("button", name=re.compile(r"qr\s*code", re.I)).first
    qr_btn.click(timeout=6000)

    logger.info("QR DOM [2/5] : attente de la modale QR code...")
    dlg = page.locator('[role="dialog"]:visible').last
    dlg.wait_for(state="visible", timeout=6000)

    logger.info("QR DOM [3/5] : saisie du PIN éphémère...")
    pin_input = dlg.locator("input").first
    pin_input.wait_for(state="visible", timeout=5000)
    pin_input.fill(pin, timeout=5000)

    logger.info("QR DOM [4/5] : clic sur Générer...")
    gen_btn = dlg.get_by_role("button", name=re.compile(r"générer", re.I)).first
    gen_btn.click(timeout=6000)

    logger.info("QR DOM [5/5] : attente de l'image QR...")
    qr_img = dlg.locator('img[src^="data:image/png"]').first
    qr_img.wait_for(state="visible", timeout=8000)
    logger.info("QR DOM [5a] : image QR visible, tentative décodage natif navigateur...")
    qr_data: Optional[Dict[str, Any]] = None
    try:
        raw_js = qr_img.evaluate(
            """async (img) => {
                if (!('BarcodeDetector' in window)) return null;
                try {
                    const det = new BarcodeDetector({ formats: ['qr_code'] });
                    const res = await det.detect(img);
                    return res && res.length ? res[0].rawValue : null;
                } catch (e) {
                    return null;
                }
            }"""
        )
        if isinstance(raw_js, str) and raw_js.strip().startswith("{"):
            qr_data = json.loads(raw_js)
    except Exception:
        qr_data = None

    if qr_data is None:
        logger.info("QR DOM [5b] : repli sur décodage OpenCV...")
        src = qr_img.get_attribute("src", timeout=5000) or ""
        qr_data = _decode_qr_data_url(src)
    logger.info("QR Code Pronote décodé avec succès (url=%s).", qr_data.get("url"))
    return qr_data


_PIN_CAPTURE_INIT_SCRIPT = """(() => {
  if (!window.__pronoteMcpBannerScheduled) {
    window.__pronoteMcpBannerScheduled = true;
    const showBanner = () => {
      if (!document.body || document.getElementById('pronote-mcp-info-banner')) return;
      const bar = document.createElement('div');
      bar.id = 'pronote-mcp-info-banner';
      bar.style.cssText = 'position:fixed;bottom:14px;right:14px;max-width:440px;z-index:2147483646;background:#0f172a;color:#f8fafc;padding:10px 14px;border-radius:10px;font:500 12.5px/1.45 system-ui,sans-serif;display:flex;gap:10px;align-items:flex-start;box-shadow:0 8px 24px rgba(0,0,0,.28);border:1px solid #334155;';
      bar.innerHTML = '<span><strong style="color:#34d399;">Pronote MCP</strong> : Connectez-vous normalement (ENT, identifiants, 2FA…). Une fois sur l\\'accueil Pronote, des actions automatiques vont récupérer le 2FA et générer le jeton de connexion sans fermer votre session prématurément.</span><button style="background:transparent;color:#94a3b8;border:none;font-size:16px;line-height:1;cursor:pointer;padding:0 2px;" title="Fermer" onclick="this.parentElement.remove()">×</button>';
      document.body.appendChild(bar);
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', showBanner, { once: true });
    } else {
      showBanner();
    }
  }
  if (window.__pronoteMcpPinHooked) return;
  window.__pronoteMcpPinHooked = true;
  window.__pronoteMcp2faPin = "";
  document.addEventListener("click", (ev) => {
    const target = ev.target && ev.target.closest ? ev.target.closest("button") : null;
    if (!target) return;
    const dlg = target.closest('.ObjetFenetre_PIN_racine, [role="dialog"]');
    if (!dlg) return;
    const dlgText = (dlg.innerText || "").toLowerCase();
    if (!dlgText.includes("code pin")) return;
    const label = (target.innerText || target.textContent || "").trim();
    const aria = (target.getAttribute("aria-label") || "").toLowerCase();
    if (/^[0-9]$/.test(label)) {
      if (window.__pronoteMcp2faPin.length >= 4) {
        window.__pronoteMcp2faPin = label;
      } else {
        window.__pronoteMcp2faPin += label;
      }
    } else if (label.toLowerCase().includes("effacer") || aria.includes("effacer") || label.toLowerCase().includes("annuler")) {
      window.__pronoteMcp2faPin = "";
    }
  }, true);
})();"""


def _read_captured_2fa_pin(page: Any) -> Optional[str]:
    """Read a 4-digit 2FA PIN captured from Pronote's keypad modal, if any."""
    try:
        val = page.evaluate("() => window.__pronoteMcp2faPin || ''")
        if isinstance(val, str) and len(val) == 4 and val.isdigit():
            return val
    except Exception:
        pass
    return None


def _inject_qr_fallback_banner(page: Any) -> None:
    """Display a non-intrusive helper banner in the open Pronote tab when SSO cookies are unavailable."""
    try:
        page.evaluate(
            """() => {
                if (document.getElementById('pronote-mcp-qr-banner')) return;
                const bar = document.createElement('div');
                bar.id = 'pronote-mcp-qr-banner';
                bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;background:#0f766e;color:#fff;padding:10px 16px;font:600 13px/1.4 system-ui,sans-serif;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,.25);';
                bar.innerHTML = '<span><strong>Pronote MCP :</strong> Connexion directe (sans ENT). Votre session reste ouverte ici pour accéder à <em>Mon compte → QR Code</em> (ou utilisez l\\'onglet Identifiants dans l\\'assistant).</span><button style="margin-left:12px;background:#fff;color:#0f766e;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-weight:700;" onclick="this.parentElement.remove()">OK</button>';
                document.body.appendChild(bar);
            }"""
        )
    except Exception:
        pass


def authenticate_via_browser(
    target_url: str,
    account_type: str = "student",
    account_pin: str = "",
    device_name: str = "MCP Assistant",
    env_path: Optional[Path] = None,
    timeout_seconds: int = 180,
    cookies_connector: Optional[Callable[..., Any]] = None,
) -> PronoteSettings:
    """Open the official Pronote/ENT page in Edge/Chrome, wait for user login, and persist a token."""
    log_file = (env_path.parent / "sso_debug.log") if env_path else _SSO_LOG_FILE
    log = get_sso_logger(log_file)
    clean_url = target_url.strip()
    parsed = urlparse(clean_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL invalide (elle doit commencer par https:// ou http://).")

    log.info("=== Début authentification navigateur SSO ===")
    log.info("URL cible=%s | account_type=%s | pin_2fa_fourni=%s | env_path=%s", clean_url, account_type, bool(account_pin.strip()), env_path)

    from playwright.sync_api import sync_playwright
    import pronotepy
    from pronote_mcp.client import PronoteSessionManager

    result_event = threading.Event()
    result_box: Dict[str, Any] = {}

    def _keep_browser_open_until_closed(context: Any) -> None:
        log.info("Navigateur maintenu ouvert pour permettre l'accès à Mon compte → QR Code.")
        while True:
            open_pages = [pg for pg in context.pages if not pg.is_closed()]
            if not open_pages:
                break
            try:
                open_pages[0].wait_for_timeout(1000)
            except Exception:
                break
        log.info("Navigateur fermé par l'utilisateur.")

    def _worker() -> None:
        final_url = clean_url
        raw_cookies: list[dict[str, Any]] = []
        keep_open = False
        try:
            with sync_playwright() as p:
                browser, context = _launch_browser_context(p, logger=log)
                try:
                    context.add_init_script(_PIN_CAPTURE_INIT_SCRIPT)
                    page = context.pages[0] if context.pages else context.new_page()
                    log.info("Navigation vers %s ...", clean_url)
                    page.goto(clean_url, wait_until="domcontentloaded")

                    matched_page = None
                    captured_2fa_pin: Optional[str] = None
                    elapsed = 0.0
                    step = 0.75
                    last_snapshot_sig: Optional[str] = None
                    while elapsed < timeout_seconds:
                        pages = [pg for pg in context.pages if not pg.is_closed()]
                        if not pages:
                            log.warning("Toutes les pages du navigateur ont été fermées à t=%.2fs.", elapsed)
                            raise RuntimeError("Fenêtre du navigateur fermée avant la fin de la connexion.")

                        for idx, pg in enumerate(pages):
                            diag = _inspect_pronote_page(pg)
                            sig = f"p{idx}:{diag.get('url')}|{diag.get('title')}|pwd={diag.get('pwdVisible')}|modals={len(diag.get('visibleModals', []))}|dash={diag.get('dashboardCount')}|auth={diag.get('authenticated')}"
                            if sig != last_snapshot_sig:
                                log.debug("État page[%d] t=%.2fs: %s | modals=%s | bodyLen=%s", idx, elapsed, sig, diag.get("visibleModals"), diag.get("bodyLen"))
                                last_snapshot_sig = sig
                            maybe_pin = _read_captured_2fa_pin(pg)
                            if maybe_pin and maybe_pin != captured_2fa_pin:
                                captured_2fa_pin = maybe_pin
                                log.info("Code PIN 2FA détecté automatiquement lors de la saisie dans Edge.")
                            if diag.get("authenticated"):
                                matched_page = pg
                                log.info("Page authentifiée détectée à t=%.2fs: %s (title=%r)", elapsed, diag.get("url"), diag.get("title"))
                                break

                        if matched_page is not None:
                            final_url = _normalize_pronote_space_url(matched_page.url, account_type)
                            raw_cookies = context.cookies()
                            cookie_summary = [
                                f"{c.get('name')}@{c.get('domain')}{c.get('path')} (len={len(c.get('value', ''))}, httpOnly={c.get('httpOnly')}, secure={c.get('secure')})"
                                for c in raw_cookies
                            ]
                            log.info("Cookies capturés (%d): %s", len(raw_cookies), cookie_summary)
                            break
                        try:
                            pages[0].wait_for_timeout(int(step * 1000))
                        except Exception as exc:
                            log.warning("wait_for_timeout interrompu à t=%.2fs: %r", elapsed, exc)
                            if not [pg for pg in context.pages if not pg.is_closed()]:
                                raise RuntimeError("Fenêtre du navigateur fermée avant la fin de la connexion.")
                        elapsed += step
                    else:
                        log.error("Timeout après %ds en attendant la connexion.", timeout_seconds)
                        raise TimeoutError("Délai dépassé en attendant la connexion sur la page Pronote.")

                    jar = cookies_to_jar(raw_cookies)
                    log.info("CookieJar construit: %d cookie(s). final_url=%s", len(jar), final_url)
                    is_parent = account_type == "parent"
                    client_cls = pronotepy.ParentClient if is_parent else pronotepy.Client
                    pin_2fa = account_pin.strip() or captured_2fa_pin or None
                    if not account_pin.strip() and captured_2fa_pin:
                        log.info("Utilisation du PIN 2FA capturé automatiquement pour l'enregistrement .env.")
                    stable_uuid = uuid_lib.uuid4().hex
                    dev_name = device_name.strip() or "MCP Assistant"
                    ephemeral_pin = f"{random.randint(0, 9999):04d}"

                    tok_client = None
                    if len(jar) > 0:
                        try:
                            log.info("Tentative reprise session pronotepy (%s) via cookies...", client_cls.__name__)
                            if cookies_connector is not None:
                                client = cookies_connector(final_url, jar)
                            else:
                                client = client_cls(
                                    pronote_url=final_url,
                                    username="sso",
                                    password="sso",
                                    ent=lambda _u, _p, **_kw: jar,
                                    uuid=stable_uuid,
                                    account_pin=pin_2fa,
                                    device_name=dev_name,
                                )
                            if getattr(client, "logged_in", False):
                                log.info("Session SSO ENT reprise, conversion en jeton durable...")
                                qr_data = client.request_qr_code_data(ephemeral_pin)
                                tok_client = client_cls.qrcode_login(
                                    qr_code=qr_data,
                                    pin=ephemeral_pin,
                                    uuid=stable_uuid,
                                    account_pin=pin_2fa,
                                    device_name=dev_name,
                                )
                        except Exception as exc:
                            log.info("Reprise par cookies non applicable (%s), bascule sur capture QR DOM.", exc)

                    if tok_client is None:
                        if matched_page is None:
                            raise ConnectionError("Page Pronote authentifiée introuvable pour générer le QR Code.")
                        qr_data = _extract_qr_via_browser_dom(matched_page, ephemeral_pin, log)
                        tok_client = client_cls.qrcode_login(
                            qr_code=qr_data,
                            pin=ephemeral_pin,
                            uuid=stable_uuid,
                            account_pin=pin_2fa,
                            device_name=dev_name,
                        )

                    creds = tok_client.export_credentials()
                    log.info("Jeton durable obtenu avec succès (username=%s, url=%s).", creds.get("username"), creds.get("url"))

                    payload: Dict[str, str] = {
                        "PRONOTE_URL": str(creds.get("url") or final_url),
                        "PRONOTE_USERNAME": str(creds.get("username") or getattr(tok_client, "username", "")),
                        "PRONOTE_TOKEN": str(creds.get("password") or getattr(tok_client, "password", "")),
                        "PRONOTE_UUID": str(creds.get("uuid") or stable_uuid),
                        "PRONOTE_ACCOUNT_TYPE": "parent" if is_parent else "student",
                        "PRONOTE_DEVICE_NAME": dev_name,
                    }
                    if pin_2fa:
                        payload["PRONOTE_ACCOUNT_PIN"] = pin_2fa

                    target_env = save_env_config(payload, env_path=env_path)
                    saved = PronoteSettings(_env_file=str(target_env))
                    PronoteSessionManager(saved)._save_cached_session(tok_client)
                    log.info("=== Authentification navigateur SSO terminée et enregistrée dans %s ===", target_env)
                    result_box["settings"] = saved
                    result_event.set()
                finally:
                    if browser is not None:
                        browser.close()
                    else:
                        context.close()
                    if not keep_open:
                        log.info("Navigateur fermé.")
        except Exception as exc:
            if not result_event.is_set():
                result_box["error"] = exc
                result_event.set()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    if not result_event.wait(timeout=timeout_seconds + 15):
        raise TimeoutError("Délai dépassé en attendant l'authentification navigateur.")
    if "error" in result_box:
        raise result_box["error"]
    return result_box["settings"]
