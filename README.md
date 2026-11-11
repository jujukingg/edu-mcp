# Pronote MCP Server

Serveur MCP (Model Context Protocol) haute performance pour connecter l'IA Antigravity Gemini à l'espace Pronote élève et parent via pronotepy.

## 🌟 Fonctionnalités

- **Session persistante & Anti-Alerte** : Cache local de session (`.session_cache.pkl`) et identifiant matériel fixe (`.device_uuid`) évitant les alertes répétées par mail/SMS de nouvelle connexion.
- **Double Authentification (2FA)** : Support natif du code PIN à 4 chiffres et nom d'appareil personnalisé.
- **Bypass SSL Windows** : Injection automatique des certificats de confiance système via `truststore` pour pallier les erreurs SSL courantes sous Windows.
- **Support Élève & Parent** : Navigation multi-enfants et basculement automatique.
- **12 Outils MCP** :
  - `pronote_get_user_info` : Profil, classe, établissement, statut.
  - `pronote_list_children` : Liste des enfants reliés (compte parent).
  - `pronote_select_child` : Sélection de l'enfant actif.
  - `pronote_list_ents` : Liste des ENT supportés.
  - `pronote_get_timetable` : Emploi du temps par plage de dates.
  - `pronote_get_homework` : Cahier de texte et devoirs à faire.
  - `pronote_set_homework_done` : Validation d'un devoir fait.
  - `pronote_get_grades` : Notes et évaluations individuelles.
  - `pronote_get_averages` : Moyennes de l'élève et de la classe.
  - `pronote_get_absences` : Absences, retards et punitions.
  - `pronote_get_news` : Actualités et sondages de l'établissement.
  - `pronote_get_canteen_menu` : Menus de la cantine scolaire.
- **4 Ressources MCP** :
  - `pronote://student/profile`
  - `pronote://timetable/today`
  - `pronote://homework/pending`
  - `pronote://grades/overview`
- **2 Prompts MCP** :
  - `pronote_daily_briefing` : Briefing complet du matin.
  - `pronote_homework_planner` : Planificateur de travail et révisions.

## 🚀 Installation & Configuration

### 1. Prérequis
- Python 3.10+
- Accès internet vers votre instance Pronote

### 2. Configuration (`.env`)
Copiez `.env.example` en `.env` et complétez vos identifiants :
```env
PRONOTE_URL=https://demo.pronote.index-education.net/pronote/eleve.html
PRONOTE_USERNAME=votre_identifiant
PRONOTE_PASSWORD=votre_mot_de_passe
PRONOTE_ACCOUNT_PIN=0000
PRONOTE_DEVICE_NAME=Mon Appareil MCP
PRONOTE_ACCOUNT_TYPE=student
PRONOTE_SESSION_FILE=.session_cache.pkl
```

### 3. Intégration dans un client MCP (`mcp_config.json` ou `claude_desktop_config.json`)

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

> **Note Windows** : Indiquez le chemin absolu vers le dossier du projet (ex. `"C:\\projets\\pronote_mcp"`).
```

### 4. Tests
```powershell
.\venv\Scripts\pytest -v
```
