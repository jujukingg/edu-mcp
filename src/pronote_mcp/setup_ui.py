"""Local secure GUI popup for configuring Pronote credentials without exposing secrets to chat."""

from pathlib import Path
from typing import Dict, List, Optional
from pronote_mcp.config import PronoteSettings, save_env_config


class HeadlessEnvironmentError(RuntimeError):
    """Raised when a GUI popup cannot be opened (no display or tkinter missing)."""


def open_setup_popup(
    env_path: Optional[Path] = None,
    ent_choices: Optional[List[str]] = None,
    initial_values: Optional[Dict[str, str]] = None,
) -> Optional[PronoteSettings]:
    """Open a local tkinter window to collect Pronote credentials and save them to .env.

    Returns a validated PronoteSettings instance on save, or None if cancelled.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as exc:
        raise HeadlessEnvironmentError(
            "Interface graphique indisponible (tkinter manquant). "
            "Configurez le fichier .env manuellement sans partager vos identifiants dans le chat."
        ) from exc

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise HeadlessEnvironmentError(
            "Aucun affichage graphique disponible pour ouvrir la popup sécurisée. "
            "Configurez le fichier .env manuellement sans partager vos identifiants dans le chat."
        ) from exc

    defaults = initial_values or {}
    saved_settings: Optional[PronoteSettings] = None

    root.title("Pronote MCP — Configuration sécurisée")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = ttk.Frame(root, padding=16)
    frame.grid(row=0, column=0, sticky="nsew")

    ttk.Label(
        frame,
        text="Vos identifiants sont enregistrés uniquement dans le fichier local .env.\n"
        "Aucune donnée sensible n'est transmise au chat ou au modèle IA.",
        justify="left",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

    url_var = tk.StringVar(value=defaults.get("PRONOTE_URL", ""))
    type_var = tk.StringVar(value=defaults.get("PRONOTE_ACCOUNT_TYPE", "student"))
    ent_var = tk.StringVar(value=defaults.get("PRONOTE_ENT", ""))
    user_var = tk.StringVar(value=defaults.get("PRONOTE_USERNAME", ""))
    pass_var = tk.StringVar(value="")
    pin_var = tk.StringVar(value="")
    device_var = tk.StringVar(value=defaults.get("PRONOTE_DEVICE_NAME", "MCP Assistant"))

    fields = [
        ("URL Pronote *", url_var, False),
        ("Identifiant *", user_var, False),
        ("Mot de passe *", pass_var, True),
        ("Code PIN 2FA (optionnel)", pin_var, True),
        ("Nom de l'appareil", device_var, False),
    ]

    row_idx = 1
    ttk.Label(frame, text="Type de compte").grid(row=row_idx, column=0, sticky="w", pady=4)
    type_combo = ttk.Combobox(frame, textvariable=type_var, values=["student", "parent"], state="readonly", width=38)
    type_combo.grid(row=row_idx, column=1, sticky="ew", pady=4)
    row_idx += 1

    ttk.Label(frame, text="ENT (optionnel)").grid(row=row_idx, column=0, sticky="w", pady=4)
    ent_values = [""] + sorted(ent_choices or [])
    ent_combo = ttk.Combobox(frame, textvariable=ent_var, values=ent_values, width=38)
    ent_combo.grid(row=row_idx, column=1, sticky="ew", pady=4)
    row_idx += 1

    for label, var, is_secret in fields:
        ttk.Label(frame, text=label).grid(row=row_idx, column=0, sticky="w", pady=4, padx=(0, 8))
        entry = ttk.Entry(frame, textvariable=var, width=41, show="•" if is_secret else "")
        entry.grid(row=row_idx, column=1, sticky="ew", pady=4)
        row_idx += 1

    def _on_save() -> None:
        nonlocal saved_settings
        url = url_var.get().strip()
        username = user_var.get().strip()
        password = pass_var.get()
        if not url or not username or not password:
            messagebox.showerror("Champs requis", "Veuillez renseigner l'URL Pronote, l'identifiant et le mot de passe.", parent=root)
            return

        payload: Dict[str, str] = {
            "PRONOTE_URL": url,
            "PRONOTE_ACCOUNT_TYPE": type_var.get().strip() or "student",
            "PRONOTE_ENT": ent_var.get().strip(),
            "PRONOTE_USERNAME": username,
            "PRONOTE_PASSWORD": password,
            "PRONOTE_DEVICE_NAME": device_var.get().strip() or "MCP Assistant",
        }
        pin = pin_var.get().strip()
        if pin:
            payload["PRONOTE_ACCOUNT_PIN"] = pin

        target_path = save_env_config(payload, env_path=env_path)
        saved_settings = PronoteSettings(_env_file=str(target_path))
        root.destroy()

    def _on_cancel() -> None:
        root.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=row_idx, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btn_frame, text="Annuler", command=_on_cancel).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(btn_frame, text="Enregistrer dans .env", command=_on_save).grid(row=0, column=1)

    root.protocol("WM_DELETE_WINDOW", _on_cancel)
    root.mainloop()
    return saved_settings
