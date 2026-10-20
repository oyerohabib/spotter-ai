from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import AnalyzeError, analyze_routes


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class AnalyzeRoutesView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            result = analyze_routes(request.data if isinstance(request.data, dict) else {})
        except AnalyzeError as exc:
            return Response({"detail": str(exc)}, status=exc.status)
        except Exception as exc:  # pragma: no cover - unexpected
            return Response(
                {"detail": f"Unexpected error: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(result)
