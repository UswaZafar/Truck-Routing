from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TripPlan
from .serializers import GeocodeQuerySerializer, TripPlanRequestSerializer, TripPlanSerializer
from .services.geocoding import GeocodingClient
from .services.heatmap import build_heatmap
from .services.planner import compute_plan, resolve_places
from .services.weather import WeatherClient


class TripPlanViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    POST /api/trip-plans/                 → compute and store a plan (201)
    GET  /api/trip-plans/{id}/            → stored plan
    GET  /api/trip-plans/{id}/heatmap/    → corridor heatmap for hours 0–48 after departure
    """

    queryset = TripPlan.objects.all()
    serializer_class = TripPlanSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "heatmap":
            return queryset.only("id", "departure_at", "load_weight_lb", "result", "heatmap")
        return queryset.defer("heatmap")

    def get_serializer_class(self):
        return TripPlanRequestSerializer if self.action == "create" else TripPlanSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        origin, destination = resolve_places(params["origin"], params["destination"])
        result = compute_plan(
            origin=origin,
            destination=destination,
            departure_at=params["departure_at"],
            load_weight_lb=params["load_weight_lb"],
            interval_miles=params["interval_miles"],
        )
        plan = TripPlan.objects.create(
            origin=origin,
            destination=destination,
            departure_at=params["departure_at"],
            load_weight_lb=params["load_weight_lb"],
            interval_miles=params["interval_miles"],
            result=result,
        )
        return Response(TripPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def heatmap(self, request, pk=None):
        plan = self.get_object()
        if plan.heatmap is None:
            lines = [[(lat, lng) for lng, lat in route["geometry"]] for route in plan.result["routes"]]
            plan.heatmap = build_heatmap(
                lines, plan.departure_at, plan.load_weight_lb, WeatherClient(), settings.HEATMAP_MAX_CELLS
            )
            plan.save(update_fields=["heatmap"])
        response = Response(plan.heatmap)
        response["Cache-Control"] = "private, max-age=900"
        return response


class GeocodeView(APIView):
    """GET /api/geocode/?q=… → up to five place suggestions."""

    def get(self, request):
        query = GeocodeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        results = GeocodingClient().search(query.validated_data["q"])
        response = Response({"results": results})
        response["Cache-Control"] = "public, max-age=3600"
        return response
