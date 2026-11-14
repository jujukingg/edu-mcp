<p align="center">
  <img src="assets/logo.png" alt="Pronote MCP" width="96" />
</p>

<h1 align="center">Pronote MCP</h1>

<p align="center">
  Serveur Model Context Protocol (MCP) pour la consultation et l'interaction avec les espaces Pronote (élève et parent).
</p>

Le serveur s'appuie sur `FastMCP`, `pronotepy` et `pydantic` pour exposer les données scolaires sous forme d'outils, de ressources et de modèles de prompts standardisés.

---

## Caractéristiques techniques

- **Gestion de session persistante** : Sauvegarde locale de l'état d'authentification (`.session_cache.pkl`) et identifiant matériel fixe (`.device_uuid`) afin d'éviter les alertes de sécurité répétées lors des reconnexions.
- **Heartbeat en tâche de fond** : Maintien de la session active via un thread démon pour les requêtes espacées dans le temps.
- **Prise en charge des certificats système** : Intégration de `truststore` pour résoudre les erreurs de validation SSL sur les environnements Windows protégés par antivirus ou pare-feu applicatif.
- **Double espace élève / parent** : Prise en charge des comptes élèves ainsi que des comptes parents avec sélection d'enfant.
- **Typage strict** : Validation de toutes les entrées et sorties via des modèles Pydantic immuables.

---

## Outils disponibles

| Outil | Description |
|---|---|
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
| `pronote_setup_account` | Ouvre une fenêtre locale sécurisée pour configurer `.env` sans exposer les identifiants dans le chat. |

---

## Ressources et Prompts

### Ressources

- `pronote://student/profile` : Profil et métadonnées de scolarité (JSON).
- `pronote://timetable/today` : Emploi du temps et contenus de séance du jour (JSON).
- `pronote://homework/pending` : Devoirs non effectués à échéance de 14 jours (JSON).
- `pronote://grades/overview` : Synthèse globale des moyennes de périodes (JSON).
- `pronote://messages/unread` : Fils de discussion non lus en lecture seule (JSON).
- `pronote://academics/weekly-radar` : Synthèse hebdomadaire devoirs et alertes d'emploi du temps (JSON).

### Prompts

- `pronote_daily_briefing` : Modèle de synthèse matinale (cours, devoirs du jour, messages non lus, repas et actualités).
- `pronote_homework_planner` : Modèle d'organisation et de priorisation des révisions.
- `pronote_period_review` : Bilan complet de période (progression, compétences, bulletin et assiduité).

---

## Configuration

Copier le fichier d'exemple pour définir vos variables locales :

```bash
cp .env.example .env
```

### Variables principales

| Variable | Description |
|---|---|
| `PRONOTE_URL` | URL complète de l'espace Pronote (ex. `https://demo.pronote.index-education.net/pronote/eleve.html`). |
| `PRONOTE_USERNAME` | Identifiant de connexion direct ou ENT. |
| `PRONOTE_PASSWORD` | Mot de passe associé. |
| `PRONOTE_ENT` | Identifiant du connecteur ENT (optionnel, ex. `monbureaunumerique`, `ile_de_france`). |
| `PRONOTE_ACCOUNT_PIN` | Code PIN à 4 chiffres en cas de double authentification. |
| `PRONOTE_DEVICE_NAME` | Nom d'appareil affiché dans Pronote (défaut : `MCP Assistant`). |
| `PRONOTE_ACCOUNT_TYPE` | Type de compte : `student` ou `parent`. |
| `PRONOTE_SESSION_FILE` | Emplacement du cache de session local (défaut : `.session_cache.pkl`). |
| `PRONOTE_DOWNLOAD_DIR` | Dossier local de sauvegarde des pièces jointes et exports (défaut : `./downloads`). |

---

## Intégration client MCP

Exemple de bloc de configuration pour `mcp_config.json` ou `claude_desktop_config.json` :

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

*Sous Windows, remplacer le chemin par le dossier absolu correspondant, par exemple `"C:\\projets\\pronote_mcp"`.*

---

## Tests

Pour exécuter les tests unitaires :

```bash
pytest -v
```

---

## Licence

Ce projet est distribué sous licence MIT.
