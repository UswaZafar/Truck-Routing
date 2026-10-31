from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import GeocodeView, TripPlanViewSet

router = SimpleRouter()
router.register("trip-plans", TripPlanViewSet, basename="trip-plan")

urlpatterns = [
    path("geocode/", GeocodeView.as_view(), name="geocode"),
    *router.urls,
]
