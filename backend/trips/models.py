import uuid

from django.db import models


class TripPlan(models.Model):
    """A computed trip plan: the user's inputs plus the routes, checkpoints and recommendation.

    Results are stored as JSON because they are immutable, always read as a whole and never filtered on;
    persisting them lets the heatmap endpoint reuse the route geometry from any worker process.
    """

    class Interval(models.IntegerChoices):
        TEN = 10, "10 miles"
        TWENTY_FIVE = 25, "25 miles"
        FIFTY = 50, "50 miles"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    origin = models.JSONField()
    destination = models.JSONField()
    departure_at = models.DateTimeField()
    load_weight_lb = models.PositiveIntegerField()
    interval_miles = models.PositiveSmallIntegerField(choices=Interval.choices)
    result = models.JSONField()
    heatmap = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.origin.get('label')} → {self.destination.get('label')} @ {self.departure_at:%Y-%m-%d %H:%M}"
