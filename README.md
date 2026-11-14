<p align="center">
  <img src="assets/logo.png" alt="Pronote MCP" width="96" />
</p>

<h1 align="center">Pronote MCP</h1>

<p align="center">
  <strong>🇫🇷 Serveur MCP (Model Context Protocol) pour Pronote (élève & parent)</strong><br />
  <strong>🇬🇧 Model Context Protocol (MCP) server for Pronote (student & parent spaces)</strong>
</p>

<p align="center">
  Compatible with <strong>Claude Desktop</strong>, <strong>Cursor</strong>, and <strong>Antigravity</strong> via <code>uvx pronote-mcp</code>.
</p>

---

## 🇫🇷 Démarrage rapide / 🇬🇧 Quick Start

### 1. Installation (1 ligne / 1 line)

Avec [`uv`](https://docs.astral.sh/uv/) *(recommandé / recommended)* :

```bash
uvx pronote-mcp
```

Ou via `pip` :

```bash
pip install pronote-mcp
```

### 2. Configuration client MCP (Claude Desktop, Cursor, Antigravity)

Ajoutez ce bloc dans votre fichier de configuration MCP (`claude_desktop_config.json`, `.cursor/mcp.json`, ou `mcp_config.json`) :

```json
{
  "mcpServers": {
    "pronote": {
      "command": "uvx",
      "args": ["pronote-mcp"]
    }
  }
}
```

<details>
<summary>Alternative depuis un clone local / Local git clone configuration</summary>

```json
{
  "mcpServers": {
    "pronote": {
      "command": "python",
      "args": ["-m", "pronote_mcp"],
      "cwd": "/chemin/vers/pronote_mcp"
    }
  }
}
```

</details>

### 3. Connexion guidée dans le chat / Chat-Guided Login

Une fois le serveur MCP ajouté, demandez simplement à votre assistant :

> *"Connecte mon compte Pronote"* / *"Connect my Pronote account"*

1. L'assistant vous explique le fonctionnement et vous demande votre **URL Pronote** (ex. `https://xxx.index-education.net/pronote/eleve.html` ou `parent.html`).
2. `pronote_setup_account` ouvre automatiquement votre navigateur (Edge / Chrome / Chromium) sur la page officielle de votre établissement.
3. Vous vous connectez normalement (ENT, identifiant, mot de passe, code PIN 2FA). **Aucun mot de passe ne transite par le chat.**
4. Le connecteur capture automatiquement le jeton durable (et le PIN 2FA si saisi) et le sauvegarde dans `~/.pronote_mcp/.env` (ou le `.env` local s'il existe).

---

## Caractéristiques / Features

- **Connexion SSO / ENT & 2FA automatique** : Ouverture du navigateur système via Playwright, capture automatique du PIN 2FA et conversion en jeton durable (`PRONOTE_TOKEN`).
- **Compatible `uvx` & multi-clients** : Stockage sécurisé de la configuration, du cache de session (`.session_cache.pkl`) et de l'UUID appareil (`.device_uuid`) dans `~/.pronote_mcp/` (avec priorité au `.env` local si présent).
- **Session persistante & heartbeat** : Maintien de la session active en tâche de fond pour éviter les alertes de nouvelle connexion.
- **Certificats système (`truststore`)** : Résout les erreurs SSL sous Windows (antivirus / pare-feu d'entreprise ou scolaire).
- **Double espace élève / parent** : Prise en charge des comptes élèves et parents avec sélection d'enfant (`pronote_list_children` / `pronote_select_child`).
- **Messagerie en lecture seule** : Consultation des discussions sans risque d'envoi accidentel par l'IA.

---

## Outils disponibles / Available Tools

| Outil / Tool | Description |
|---|---|
| `pronote_setup_account` | Lance la connexion guidée par navigateur officiel (ENT/SSO/2FA) et enregistre un jeton durable sans exposer vos identifiants dans le chat. |
| `pronote_get_user_info` | Récupère les données du compte actif (nom, classe, établissement). |
| `pronote_get_timetable` | Liste l'emploi du temps et le contenu pédagogique des séances pour une période donnée. |
| `pronote_get_homework` | Liste le cahier de texte et les devoirs à rendre. |
| `pronote_set_homework_done` | Marque un devoir comme effectué ou à faire. |
| `pronote_get_grades` | Retourne les évaluations et notes individuelles par période. |
| `pronote_get_averages` | Retourne les moyennes de l'élève et de la classe par matière. |
| `pronote_get_evaluations` | Liste les évaluations par compétences et niveaux d'acquisition. |
| `pronote_get_report` | Récupère les appréciations générales et par matière du bulletin. |
| `pronote_get_teaching_staff` | Liste l'équipe pédagogique et les matières associées. |
| `pronote_get_absences` | Liste les absences, retards et punitions. |
| `pronote_get_canteen_menu` | Affiche les menus de la cantine par catégorie de plat. |
| `pronote_get_news` | Liste les communications, pièces jointes et sondages de l'établissement. |
| `pronote_get_discussions` | Liste les fils de discussion de la messagerie (lecture seule). |
| `pronote_get_discussion_messages` | Lit les messages d'un fil de discussion (lecture seule). |
| `pronote_download_attachment` | Télécharge une pièce jointe (devoir, séance ou actualité) dans le dossier local configuré. |
| `pronote_export_ical` | Exporte l'emploi du temps au format iCalendar (`.ics`). |
| `pronote_export_timetable_pdf` | Génère et sauvegarde l'emploi du temps hebdomadaire au format PDF. |
| `pronote_simulate_grade` | Simule l'impact d'une note hypothétique sur la moyenne de matière et générale. |
| `pronote_analyze_progression` | Compare les moyennes entre deux périodes et face aux moyennes de classe. |
| `pronote_weekly_radar` | Agrège devoirs urgents, cours annulés/modifiés, contrôles et messages non lus. |
| `pronote_list_children` | Liste les enfants rattachés à un compte parent. |
| `pronote_select_child` | Sélectionne l'enfant ciblé pour les requêtes suivantes. |
| `pronote_list_ents` | Liste les fournisseurs ENT compatibles. |

---

## Ressources et Prompts / Resources & Prompts

### Ressources
- `pronote://student/profile` : Profil et métadonnées de scolarité (JSON).
- `pronote://timetable/today` : Emploi du temps et contenus de séance du jour (JSON).
- `pronote://homework/pending` : Devoirs non effectués à échéance de 14 jours (JSON).
- `pronote://grades/overview` : Synthèse globale des moyennes de périodes (JSON).
- `pronote://messages/unread` : Fils de discussion non lus en lecture seule (JSON).
- `pronote://academics/weekly-radar` : Synthèse hebdomadaire devoirs et alertes d'emploi du temps (JSON).

### Prompts
- `pronote_daily_briefing` : Synthèse matinale (cours, devoirs du jour, messages non lus, repas et actualités).
- `pronote_homework_planner` : Organisation et priorisation des révisions.
- `pronote_period_review` : Bilan complet de période (progression, compétences, bulletin et assiduité).

---

## Variables d'environnement / Environment Variables

Par défaut, la configuration est stockée dans `~/.pronote_mcp/.env` (ou `./.env` en développement local).

| Variable | Description |
|---|---|
| `PRONOTE_MCP_HOME` | Dossier racine personnalisé pour `.env`, cache et logs (défaut : `~/.pronote_mcp`). |
| `PRONOTE_ENV_FILE` | Chemin explicite vers un fichier `.env` spécifique. |
| `PRONOTE_URL` | URL complète de l'espace Pronote (`eleve.html` ou `parent.html`). |
| `PRONOTE_USERNAME` | Identifiant de connexion ou jeton. |
| `PRONOTE_TOKEN` | Jeton durable généré automatiquement lors de la connexion navigateur/QR. |
| `PRONOTE_UUID` | Identifiant unique d'appareil associé au jeton. |
| `PRONOTE_ACCOUNT_PIN` | Code PIN à 4 chiffres (2FA). |
| `PRONOTE_DEVICE_NAME` | Nom d'appareil affiché dans Pronote (défaut : `MCP Assistant`). |
| `PRONOTE_ACCOUNT_TYPE` | Type de compte : `student` ou `parent`. |
| `PRONOTE_SESSION_FILE` | Emplacement du cache de session (défaut : `~/.pronote_mcp/.session_cache.pkl`). |
| `PRONOTE_DOWNLOAD_DIR` | Dossier local des pièces jointes et exports (défaut : `./downloads`). |

---

## Tests

```bash
pip install -e ".[dev]"
pytest tests/unit -v
```

---

## Licence / License

MIT — voir [LICENSE](LICENSE).
