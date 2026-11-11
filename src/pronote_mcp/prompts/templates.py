"""Prompt templates for Pronote MCP Server."""

from typing import List
from mcp.server.fastmcp import FastMCP
from mcp.types import PromptMessage, TextContent
from pronote_mcp.client import PronoteSessionManager


def register_prompts(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register prompt templates on the MCP server."""

    @server.prompt(
        name="pronote_daily_briefing",
        description="Generate a comprehensive morning briefing: today's schedule, pending homework, menu, and recent notes.",
    )
    async def daily_briefing() -> List[PromptMessage]:
        target = await session_manager.get_active_target()
        user_name = getattr(target, "name", "l'élève")

        prompt_text = (
            f"Tu es l'assistant scolaire personnel de {user_name}.\n"
            "Génère un briefing complet et motivant pour aujourd'hui en suivant ces étapes :\n"
            "1. Utilise `pronote_get_timetable` pour lister l'emploi du temps de la journée (cours, salles, professeurs, cours annulés s'il y en a).\n"
            "2. Utilise `pronote_get_homework` pour rappeler les devoirs à rendre pour aujourd'hui et les prochains jours.\n"
            "3. Utilise `pronote_get_canteen_menu` pour afficher le menu de la cantine du midi.\n"
            "4. Utilise `pronote_get_grades` pour vérifier s'il y a eu de nouvelles notes récemment.\n"
            "5. Présente le tout de manière structurée, claire, chaleureuse et avec des conseils pratiques pour bien organiser sa journée."
        )

        return [
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=prompt_text),
            )
        ]

    @server.prompt(
        name="pronote_homework_planner",
        description="Analyze upcoming homework assignments and generate an optimized revision and study schedule.",
    )
    async def homework_planner() -> List[PromptMessage]:
        prompt_text = (
            "Tu es un coach pédagogique et d'organisation scolaire.\n"
            "Analyse l'ensemble des devoirs à venir en utilisant `pronote_get_homework` sur les 14 prochains jours.\n"
            "Ensuite, consulte l'emploi du temps avec `pronote_get_timetable` et les moyennes actuelles avec `pronote_get_averages`.\n"
            "Établis un planning de révision et de travail par ordre de priorité :\n"
            "- Identifie les devoirs urgents et les devoirs à fort coefficient / dans les matières où l'élève a besoin de soutien.\n"
            "- Découpe les projets longs en sous-tâches réalistes.\n"
            "- Propose des créneaux précis d'étude en utilisant la méthode Pomodoro."
        )

        return [
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=prompt_text),
            )
        ]
