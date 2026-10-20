from pathlib import Path

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path

FRONTEND_INDEX = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "index.html"


def spa_fallback(_request):
    if FRONTEND_INDEX.exists():
        return HttpResponse(FRONTEND_INDEX.read_text(encoding="utf-8"), content_type="text/html")
    return HttpResponse(
        "Frontend build not found. Run `cd frontend && npm run build` or use the Vite dev server.",
        status=503,
        content_type="text/plain",
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("routing.urls")),
]

urlpatterns += [
    re_path(r"^(?!api/|admin/|static/).*$", spa_fallback, name="spa"),
]
