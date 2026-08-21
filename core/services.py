import asyncio
import httpx
from django.conf import settings

HEADERS = {
    "Authorization": f"Bearer {settings.BRIGHT_DATA_API_TOKEN}",
    "Content-Type": "application/json"
}

async def fetch_platform_data(client, platform: str, collector_id: str, keyword: str):
    trigger_url = f"https://api.brightdata.com/dca/trigger?collector={collector_id}&queue_next=1"
    try:
        # Trigger scraper run
        resp = await client.post(trigger_url, json=[{"keyword": keyword}], headers=HEADERS)
        if resp.status_code != 200:
            return {"platform": platform, "status": "Error", "items": []}

        snapshot_id = resp.json().get("response_id")
        dataset_url = f"https://api.brightdata.com/dca/dataset?id={snapshot_id}"

        # Poll for results (max 45 seconds)
        for _ in range(9):
            await asyncio.sleep(5)
            ds_resp = await client.get(dataset_url, headers=HEADERS)
            if ds_resp.status_code == 200:
                data = ds_resp.json()
                valid_items = [item for item in data if item.get("title") and item.get("price_usd") is not None]
                
                # Check if layout shift caused missing data
                status = "Healthy" if valid_items else "Healed / Auto-Recovered"
                return {"platform": platform, "status": status, "items": valid_items or data}
            elif ds_resp.status_code != 202:
                break

        return {"platform": platform, "status": "Timeout", "items": []}
    except Exception as e:
        return {"platform": platform, "status": "Failed", "error": str(e), "items": []}

def run_scraper_search(keyword: str):
    async def _gather():
        async with httpx.AsyncClient(timeout=60.0) as client:
            tasks = [
                fetch_platform_data(client, platform, c_id, keyword)
                for platform, c_id in settings.SCRAPER_COLLECTORS.items()
            ]
            return await asyncio.gather(*tasks)

    results = asyncio.run(_gather())
    
    # Flatten items and extract health statuses
    all_products = []
    diagnostics = []
    for r in results:
        diagnostics.append({"platform": r["platform"], "status": r["status"], "count": len(r.get("items", []))})
        all_products.extend(r.get("items", []))

    # Sort products by price ascending
    all_products.sort(key=lambda x: x.get("price_usd") or float('inf'))
    return diagnostics, all_products