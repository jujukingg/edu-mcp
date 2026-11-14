"""Pronote session management and API bridge."""

import asyncio
import logging
import os
import pickle
import uuid
from typing import Any, Callable, Dict, List, Optional

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import pronotepy
import pronotepy.ent
from pronote_mcp.config import PronoteSettings, load_settings_or_none
from pronote_mcp.setup_ui import open_setup_popup

logger = logging.getLogger("pronote_mcp.client")


class PronoteSessionManager:
    """Manages authentication, persistent session caching, keep-alive, and student/parent context."""

    def __init__(self, settings: Optional[PronoteSettings] = None):
        self.settings: Optional[PronoteSettings] = settings
        self._client: Optional[Any] = None
        self._active_child_name: Optional[str] = settings.child_name if settings else None
        self._keep_alive_ctx: Optional[Any] = None
        self._stable_uuid = self._get_or_create_device_uuid()

    def _get_or_create_device_uuid(self) -> str:
        """Get or create a persistent device UUID to avoid triggering 'new device' alerts."""
        if self.settings and self.settings.uuid:
            return self.settings.uuid
        uuid_file = ".device_uuid"
        try:
            if os.path.exists(uuid_file):
                with open(uuid_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return content
            new_id = uuid.uuid4().hex
            with open(uuid_file, "w", encoding="utf-8") as f:
                f.write(new_id)
            return new_id
        except Exception:
            return uuid.uuid4().hex

    def _load_cached_session(self) -> Optional[Any]:
        """Attempt to restore an existing session from disk to prevent new login notifications."""
        if not self.settings:
            return None
        session_path = self.settings.session_file
        if not session_path or not os.path.exists(session_path):
            return None

        try:
            with open(session_path, "rb") as f:
                client = pickle.load(f)

            if getattr(client, "logged_in", False):
                client.session_check()
                if getattr(client, "logged_in", False):
                    logger.info("Reusing existing Pronote session from cache (no new login alert)")
                    return client
        except Exception as exc:
            logger.debug("Could not restore session from cache: %s", exc)
            self._clear_cached_session()
        return None

    def _save_cached_session(self, client: Any) -> None:
        """Save active authenticated session to disk."""
        session_path = self.settings.session_file
        if not session_path:
            return
        try:
            with open(session_path, "wb") as f:
                pickle.dump(client, f)
            logger.info("Pronote session cached successfully to %s", session_path)
        except Exception as exc:
            logger.warning("Failed to cache Pronote session to disk: %s", exc)

    def _clear_cached_session(self) -> None:
        """Clear cached session file."""
        session_path = self.settings.session_file
        if session_path and os.path.exists(session_path):
            try:
                os.remove(session_path)
            except OSError:
                pass

    def _start_keep_alive(self, client: Any) -> None:
        """Start background keep-alive heartbeat as a daemon thread."""
        if self._keep_alive_ctx is not None:
            return
        if hasattr(client, "keep_alive") and callable(client.keep_alive):
            try:
                ka = client.keep_alive()
                ka.daemon = True
                ka.start()
                self._keep_alive_ctx = ka
                logger.debug("Pronote keep-alive heartbeat started (daemon)")
            except Exception as exc:
                logger.debug("Could not start keep-alive thread: %s", exc)

    @staticmethod
    def list_supported_ents() -> List[str]:
        """List all supported ENT identity providers from pronotepy.ent."""
        ents = [
            attr
            for attr in dir(pronotepy.ent)
            if not attr.startswith("_") and callable(getattr(pronotepy.ent, attr))
        ]
        return sorted(ents)

    def _resolve_ent(self) -> Optional[Callable]:
        """Resolve ENT function from name if provided."""
        if not self.settings.ent:
            return None
        ent_name = self.settings.ent.strip()
        if not hasattr(pronotepy.ent, ent_name):
            available = self.list_supported_ents()
            raise ValueError(
                f"Unknown ENT '{ent_name}'. Supported ENTs: {', '.join(available[:10])}..."
            )
        return getattr(pronotepy.ent, ent_name)

    def _connect_sync(self) -> Any:
        """Perform login using cached session or credentials."""
        cached_client = self._load_cached_session()
        if cached_client is not None:
            self._start_keep_alive(cached_client)
            return cached_client

        ent_func = self._resolve_ent()
        is_parent = self.settings.account_type == "parent"
        client_cls = pronotepy.ParentClient if is_parent else pronotepy.Client
        pin_val = (
            self.settings.account_pin.get_secret_value()
            if self.settings.account_pin
            else None
        )
        dev_name = self.settings.device_name

        if self.settings.is_token_auth:
            token_val = self.settings.token.get_secret_value() if self.settings.token else ""
            logger.info("Connecting to Pronote using token authentication")
            client = client_cls.token_login(
                pronote_url=self.settings.url,
                username=self.settings.username or "",
                password=token_val,
                uuid=self._stable_uuid,
                account_pin=pin_val,
                device_name=dev_name,
            )
        else:
            pwd_val = self.settings.password.get_secret_value() if self.settings.password else ""
            space_name = "Parent" if is_parent else "Student"
            logger.info("Authenticating with Pronote %s space (Device: %s)", space_name, dev_name)
            client = client_cls(
                pronote_url=self.settings.url,
                username=self.settings.username or "",
                password=pwd_val,
                ent=ent_func,
                account_pin=pin_val,
                device_name=dev_name,
                uuid=self._stable_uuid,
            )

        if not getattr(client, "logged_in", False):
            raise ConnectionError("Failed to authenticate with Pronote. Check your credentials.")

        self._save_cached_session(client)
        self._start_keep_alive(client)
        return client

    async def configure_via_popup(self) -> bool:
        """Open the secure local setup popup and reload settings if saved."""
        initial: Dict[str, str] = {}
        if self.settings:
            initial = {
                "PRONOTE_URL": self.settings.url,
                "PRONOTE_ACCOUNT_TYPE": self.settings.account_type,
                "PRONOTE_ENT": self.settings.ent or "",
                "PRONOTE_USERNAME": self.settings.username or "",
                "PRONOTE_DEVICE_NAME": self.settings.device_name or "MCP Assistant",
            }
        new_settings = await asyncio.to_thread(
            open_setup_popup,
            None,
            self.list_supported_ents(),
            initial,
        )
        if new_settings is None:
            return False
        self.settings = new_settings
        self._active_child_name = new_settings.child_name
        self._client = None
        self._clear_cached_session()
        return True

    async def configure_via_browser(
        self,
        pronote_url: str,
        account_type: str = "student",
        device_name: str = "MCP Assistant",
    ) -> PronoteSettings:
        """Open the official Pronote/ENT page directly in a native browser and save a durable token."""
        from pronote_mcp.browser_auth import authenticate_via_browser

        new_settings = await asyncio.to_thread(
            authenticate_via_browser,
            target_url=pronote_url,
            account_type=account_type,
            device_name=device_name,
        )
        self.settings = new_settings
        self._active_child_name = new_settings.child_name
        self._client = None
        self._clear_cached_session()
        return new_settings

    async def ensure_configured(self) -> PronoteSettings:
        """Ensure valid PronoteSettings are loaded, or guide the AI chat to request the Pronote URL."""
        if self.settings is not None:
            return self.settings
        loaded = load_settings_or_none()
        if loaded is not None:
            self.settings = loaded
            self._active_child_name = loaded.child_name
            return loaded
        raise RuntimeError(
            "Aucun compte Pronote n'est configuré. "
            "Expliquez à l'utilisateur qu'il peut se connecter en toute sécurité sans partager son mot de passe dans le chat : "
            "demandez-lui l'URL de son espace Pronote ou ENT (ex: https://.../pronote/eleve.html) et s'il s'agit d'un compte "
            "'student' (élève) ou 'parent', puis appelez pronote_setup_account(pronote_url=..., account_type=...) "
            "pour ouvrir directement la page officielle de connexion."
        )

    async def get_client(self) -> Any:
        """Get or initialize the authenticated Pronote client."""
        await self.ensure_configured()
        if self._client is None or not getattr(self._client, "logged_in", False):
            self._client = await asyncio.to_thread(self._connect_sync)
        return self._client

    async def get_children(self) -> List[Dict[str, str]]:
        """List children for a parent account."""
        client = await self.get_client()
        if not hasattr(client, "children"):
            return []
        result = []
        for child in client.children:
            result.append(
                {
                    "name": getattr(child, "name", str(child)),
                    "class_name": getattr(child, "class_name", ""),
                    "establishment": getattr(child, "establishment", ""),
                }
            )
        return result

    async def select_child(self, child_name: str) -> bool:
        """Switch active child in parent account."""
        client = await self.get_client()
        if not hasattr(client, "children"):
            raise ValueError("Child selection is only available for parent accounts.")

        for child in client.children:
            name = getattr(child, "name", "")
            if name.lower() == child_name.lower():
                await asyncio.to_thread(client.set_child, child)
                self._active_child_name = name
                return True

        available = [getattr(c, "name", "") for c in client.children]
        raise ValueError(
            f"Child '{child_name}' not found. Available children: {', '.join(available)}"
        )

    async def get_active_target(self) -> Any:
        """Return the active student client (syncs selected child for ParentClient)."""
        client = await self.get_client()
        if self.settings.account_type == "parent" and hasattr(client, "set_child"):
            if self._active_child_name:
                await self.select_child(self._active_child_name)
            elif getattr(client, "children", None):
                first_child = client.children[0]
                await asyncio.to_thread(client.set_child, first_child)
                self._active_child_name = getattr(first_child, "name", "")
        return client

    async def execute_on_target(self, op: Callable[[Any], Any]) -> Any:
        """Execute a function on the current active target, retrying once on session expiration."""
        try:
            target = await self.get_active_target()
            return await asyncio.to_thread(op, target)
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Pronote call failed (%s), attempting reconnection...", exc)
            self._clear_cached_session()
            self._client = None
            target = await self.get_active_target()
            return await asyncio.to_thread(op, target)

    async def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Backward-compatible helper to execute a callable in a worker thread with retry."""
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Pronote call failed (%s), attempting reconnection...", exc)
            self._clear_cached_session()
            self._client = None
            await self.get_client()
            return await asyncio.to_thread(func, *args, **kwargs)
