import httpx
from tools.base import register_tool

BASE_URL = "https://api.usaspending.gov/api/v2"


def search_spending(keyword: str = "", agency: str = "", limit: int = 10) -> dict:
    payload = {
        "filters": {
            "time_period": [{"start_date": "2025-01-01", "end_date": "2026-12-31"}],
        },
        "limit": min(limit, 100),
        "page": 1,
        "sort": "Award Amount",
        "order": "desc",
    }
    if keyword:
        payload["filters"]["keywords"] = [keyword]
    if agency:
        payload["filters"]["agencies"] = [
            {"type": "awarding", "tier": "toptier", "name": agency}
        ]

    resp = httpx.post(f"{BASE_URL}/search/spending_by_award/", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    return {
        "total_results": data.get("page_metadata", {}).get("total", 0),
        "results": [
            {
                "award_id": r.get("Award ID"),
                "recipient": r.get("Recipient Name"),
                "amount": r.get("Award Amount"),
                "agency": r.get("Awarding Agency"),
                "description": (r.get("Description") or "")[:200],
                "date": r.get("Start Date"),
            }
            for r in data.get("results", [])[:limit]
        ],
    }


def get_agency_spending_summary() -> dict:
    resp = httpx.get(
        f"{BASE_URL}/references/toptier_agencies/",
        params={"sort": "obligated_amount", "order": "desc"},
        timeout=30
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])[:15]
    return {
        "agencies": [
            {
                "name": r.get("agency_name"),
                "budget": r.get("budget_authority_amount"),
                "obligated": r.get("obligated_amount"),
                "percentage": r.get("percentage_of_total_budget_authority"),
            }
            for r in results
        ]
    }


register_tool(
    agent_name="research",
    schema={
        "name": "search_spending",
        "description": "Search federal spending awards by keyword, agency, or amount",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Search keyword"},
                "agency": {"type": "string", "description": "Agency name filter"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": []
        }
    },
    execute_fn=search_spending
)

register_tool(
    agent_name="research",
    schema={
        "name": "get_agency_spending_summary",
        "description": "Get spending summary for top federal agencies",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    execute_fn=get_agency_spending_summary
)

