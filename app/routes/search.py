"""
搜索路由 v4
整合搜索历史、来源分组、引擎诊断
"""
import time
import logging
from collections import defaultdict

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from app.config import templates

from app.sources.manager import source_manager
from app.sources.parsers import PARSER_REGISTRY
from app.services.search_history import (
    add_search, get_search_history,
    delete_keyword, clear_history
)

logger = logging.getLogger(__name__)
router = APIRouter()

SOURCE_NAMES = {pid: cls.SOURCE_NAME for pid, cls in PARSER_REGISTRY.items()}


@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q:       str = Query(default=""),
    source:  str = Query(default=""),
):
    results  = []
    grouped  = {}
    error    = None
    elapsed  = 0.0
    history  = await get_search_history()

    if q.strip():
        # 异步保存搜索历史（不阻塞搜索）
        import asyncio
        asyncio.create_task(add_search(q.strip()))

        t0 = time.monotonic()
        try:
            results = await source_manager.search_all(q.strip())
        except Exception as e:
            logger.error(f"[search] 异常: {e}")
            error = f"搜索出错：{e}"
        elapsed = round(time.monotonic() - t0, 2)

        raw: dict[str, list] = defaultdict(list)
        for r in results:
            raw[r.source].append(r)

        grouped = {source: raw[source]} if (source and source in raw) else dict(raw)

    return templates.TemplateResponse(request, "search.html", {
            "query":         q,
        "results":       results,
        "grouped":       grouped,
        "source_names":  SOURCE_NAMES,
        "active_source": source,
        "error":         error,
        "elapsed":       elapsed,
        "total":         len(results),
        "history":       history
        })


# ── 搜索历史 API ──────────────────────────────────────────────────

@router.delete("/api/search-history/{keyword}")
async def del_history(keyword: str):
    await delete_keyword(keyword)
    return JSONResponse({"status": "ok"})


@router.delete("/api/search-history")
async def clear_all_history():
    await clear_history()
    return JSONResponse({"status": "ok"})


@router.get("/api/search-history")
async def list_history():
    return await get_search_history()


# ── JSON 搜索 API ─────────────────────────────────────────────────

@router.get("/api/search")
async def api_search(q: str = Query(default="")):
    if not q.strip():
        return {"results": [], "total": 0}
    results = await source_manager.search_all(q.strip())
    return {
        "query":   q,
        "total":   len(results),
        "results": [
            {"title": r.title, "author": r.author,
             "source": r.source, "source_url": r.source_url,
             "intro": r.intro}
            for r in results
        ],
    }


# ── 引擎诊断 ─────────────────────────────────────────────────────

@router.get("/debug/engines", response_class=HTMLResponse)
async def debug_engines(request: Request, q: str = Query(default="斗破苍穹")):
    import time as _time
    from app.sources.search_engines import YandexEngine, BingEngine, DuckDuckGoEngine

    reports = []
    for name, eng in [("Yandex", YandexEngine()),
                      ("Bing",   BingEngine()),
                      ("DDG",    DuckDuckGoEngine())]:
        t0 = _time.monotonic()
        try:
            res     = await eng.search(q, max_results=5)
            elapsed = round(_time.monotonic() - t0, 2)
            reports.append({"engine": name, "ok": True,
                             "count": len(res), "elapsed": elapsed,
                             "samples": [{"title": r.title, "source": r.source,
                                          "url": r.source_url} for r in res[:3]]})
        except Exception as e:
            reports.append({"engine": name, "ok": False,
                             "count": 0, "elapsed": round(_time.monotonic()-t0, 2),
                             "error": str(e), "samples": []})

    return templates.TemplateResponse(request, "debug_engines.html", {
            "query": q, "reports": reports
        })
