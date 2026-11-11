"""School life tools (absences, delays, punishments, news, canteen) for Pronote MCP Server."""

import datetime
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import (
    AbsenceDTO,
    CanteenMenuDTO,
    DelayDTO,
    NewsItemDTO,
    PunishmentDTO,
)


def register_school_life_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register school life tools on the MCP server."""

    @server.tool(
        name="pronote_get_absences",
        description="Get absences, delays (tardiness), and punishments, optionally filtered by period.",
    )
    async def pronote_get_absences(
        period_name: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        def _fetch_records(target: Any) -> Dict[str, Any]:
            abs_list: List[AbsenceDTO] = []
            del_list: List[DelayDTO] = []
            pun_list: List[PunishmentDTO] = []

            periods = getattr(target, "periods", [])
            for p in periods:
                p_name = getattr(p, "name", "")
                if period_name and period_name.lower() not in p_name.lower():
                    continue

                for a in getattr(p, "absences", []):
                    from_d = getattr(a, "from_date", "")
                    from_str = from_d.isoformat() if hasattr(from_d, "isoformat") else str(from_d)
                    to_d = getattr(a, "to_date", "")
                    to_str = to_d.isoformat() if hasattr(to_d, "isoformat") else str(to_d)
                    reasons_val = [str(r) for r in getattr(a, "reasons", [])] if getattr(a, "reasons", None) else []
                    hours_val = str(getattr(a, "hours", "")) if getattr(a, "hours", None) is not None else None

                    abs_list.append(
                        AbsenceDTO(
                            id=str(getattr(a, "id", f"abs_{from_str}_{to_str}")),
                            from_date=from_str,
                            to_date=to_str,
                            justified=bool(getattr(a, "justified", False)),
                            hours=hours_val,
                            reasons=reasons_val,
                        )
                    )

                for d in getattr(p, "delays", []):
                    d_val = getattr(d, "date", "")
                    d_str = d_val.isoformat() if hasattr(d_val, "isoformat") else str(d_val)
                    mins_val = str(getattr(d, "minutes", "")) if getattr(d, "minutes", None) is not None else None
                    del_reasons = [str(r) for r in getattr(d, "reasons", [])] if getattr(d, "reasons", None) else []

                    del_list.append(
                        DelayDTO(
                            id=str(getattr(d, "id", f"del_{d_str}")),
                            date=d_str,
                            minutes=mins_val,
                            justified=bool(getattr(d, "justified", False)),
                            reasons=del_reasons,
                        )
                    )

                for pu in getattr(p, "punishments", []):
                    pu_val = getattr(pu, "date", "")
                    pu_str = pu_val.isoformat() if hasattr(pu_val, "isoformat") else str(pu_val)
                    pu_reasons = [str(r) for r in getattr(pu, "reasons", [])] if getattr(pu, "reasons", None) else []

                    pun_list.append(
                        PunishmentDTO(
                            id=str(getattr(pu, "id", f"pun_{pu_str}")),
                            date=pu_str,
                            given_by=getattr(pu, "given_by", None),
                            reasons=pu_reasons,
                            circumstances=getattr(pu, "circumstances", None),
                            nature=getattr(pu, "nature", None),
                            duration=str(getattr(pu, "duration", "")) if getattr(pu, "duration", None) is not None else None,
                        )
                    )

            return {
                "absences": [a.model_dump() for a in abs_list],
                "delays": [d.model_dump() for d in del_list],
                "punishments": [p.model_dump() for p in pun_list],
            }

        return await session_manager.execute_on_target(_fetch_records)

    @server.tool(
        name="pronote_get_news",
        description="Get school news, announcements, and notices (defaults to last 30 days).",
    )
    async def pronote_get_news(
        date_from: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        today = datetime.date.today()
        d_from = (
            datetime.date.fromisoformat(date_from)
            if date_from
            else today - datetime.timedelta(days=30)
        )

        def _fetch_news(target: Any) -> List[NewsItemDTO]:
            items: List[NewsItemDTO] = []
            if hasattr(target, "information_and_surveys"):
                raw_info = target.information_and_surveys(d_from)
                for info in raw_info:
                    d_val = getattr(info, "creation_date", getattr(info, "date", today))
                    d_str = d_val.isoformat() if hasattr(d_val, "isoformat") else str(d_val)
                    items.append(
                        NewsItemDTO(
                            id=str(getattr(info, "id", f"news_{d_str}_{getattr(info, 'title', '')}")),
                            title=getattr(info, "title", "Information"),
                            author=getattr(info, "author", None),
                            date=d_str,
                            content=getattr(info, "content", ""),
                            category=getattr(info, "category", None),
                            read=bool(getattr(info, "read", True)),
                        )
                    )
            return sorted(items, key=lambda n: n.date, reverse=True)

        res_dtos = await session_manager.execute_on_target(_fetch_news)
        return [n.model_dump() for n in res_dtos]

    @server.tool(
        name="pronote_get_canteen_menu",
        description="Get the school cafeteria / canteen menus for a given period (defaults to current week).",
    )
    async def pronote_get_canteen_menu(
        date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        today = datetime.date.today()
        d_from = datetime.date.fromisoformat(date_from) if date_from else today
        d_to = (
            datetime.date.fromisoformat(date_to)
            if date_to
            else today + datetime.timedelta(days=7)
        )

        def _extract_dishes(meal: Any) -> List[str]:
            if not meal:
                return []
            if isinstance(meal, list):
                result = []
                for item in meal:
                    if hasattr(item, "name"):
                        result.append(item.name)
                    elif isinstance(item, list):
                        result.extend([sub.name if hasattr(sub, "name") else str(sub) for sub in item])
                    else:
                        result.append(str(item))
                return result
            if hasattr(meal, "name"):
                return [meal.name]
            return [str(meal)]

        def _fetch_menus(target: Any) -> List[CanteenMenuDTO]:
            menus: List[CanteenMenuDTO] = []
            if hasattr(target, "menus"):
                raw_menus = target.menus(d_from, d_to)
                for m in raw_menus:
                    d_val = getattr(m, "date", today)
                    d_str = d_val.isoformat() if hasattr(d_val, "isoformat") else str(d_val)
                    name_val = getattr(m, "name", "Déjeuner")

                    first = _extract_dishes(getattr(m, "first_meal", []))
                    main = _extract_dishes(getattr(m, "main_meal", []))
                    side = _extract_dishes(getattr(m, "side_meal", []))
                    cheese = _extract_dishes(getattr(m, "cheese", []))
                    dessert = _extract_dishes(getattr(m, "dessert", []))
                    all_dishes = first + main + side + cheese + dessert

                    menus.append(
                        CanteenMenuDTO(
                            date=d_str,
                            meal_name=name_val,
                            first_meal=first,
                            main_meal=main,
                            side_meal=side,
                            cheese=cheese,
                            dessert=dessert,
                            dishes=all_dishes,
                        )
                    )
            return sorted(menus, key=lambda m: m.date)

        res_dtos = await session_manager.execute_on_target(_fetch_menus)
        return [m.model_dump() for m in res_dtos]
