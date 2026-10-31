from django.urls import include, path

# The React app itself is served by WhiteNoise in production (see settings.FRONTEND_DIST).
urlpatterns = [
    path("api/", include("trips.urls")),
]
