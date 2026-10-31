from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import TripPlan

LOAD_WEIGHT_MIN_LB = 0
LOAD_WEIGHT_MAX_LB = 80_000  # US federal gross vehicle weight limit
DEPARTURE_PAST_GRACE = timedelta(hours=1)
DEPARTURE_MAX_AHEAD = timedelta(days=7)  # trip + 48 h heatmap must stay inside the 16-day forecast
PLACE_TEXT_MIN, PLACE_TEXT_MAX = 2, 200


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=PLACE_TEXT_MAX, required=False, allow_blank=True)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)


class PlaceField(serializers.Field):
    """A place given as free text (geocoded server-side) or as {label, lat, lng} picked from suggestions."""

    default_error_messages = {
        "invalid": "Enter a place name or an object with lat and lng.",
        "too_short": f"Enter at least {PLACE_TEXT_MIN} characters.",
        "too_long": f"Enter at most {PLACE_TEXT_MAX} characters.",
    }

    def to_internal_value(self, data):
        if isinstance(data, str):
            text = " ".join(data.split())
            if len(text) < PLACE_TEXT_MIN:
                self.fail("too_short")
            if len(text) > PLACE_TEXT_MAX:
                self.fail("too_long")
            return text
        if isinstance(data, dict):
            place = PlaceSerializer(data=data)
            place.is_valid(raise_exception=True)
            value = dict(place.validated_data)
            value["label"] = value.get("label") or f"{value['lat']:.4f}, {value['lng']:.4f}"
            return value
        self.fail("invalid")

    def to_representation(self, value):
        return value


class TripPlanRequestSerializer(serializers.Serializer):
    origin = PlaceField()
    destination = PlaceField()
    departure_at = serializers.DateTimeField()
    load_weight_lb = serializers.IntegerField(min_value=LOAD_WEIGHT_MIN_LB, max_value=LOAD_WEIGHT_MAX_LB)
    interval_miles = serializers.ChoiceField(choices=TripPlan.Interval.values)

    def validate_departure_at(self, value):
        now = timezone.now()
        if value < now - DEPARTURE_PAST_GRACE:
            raise serializers.ValidationError("Departure cannot be more than 1 hour in the past.")
        if value > now + DEPARTURE_MAX_AHEAD:
            raise serializers.ValidationError("Departure must be within the next 7 days (forecast range).")
        return value

    def validate(self, attrs):
        origin, destination = attrs["origin"], attrs["destination"]
        same_text = isinstance(origin, str) and isinstance(destination, str) and origin.lower() == destination.lower()
        same_point = (
            isinstance(origin, dict)
            and isinstance(destination, dict)
            and (round(origin["lat"], 4), round(origin["lng"], 4))
            == (round(destination["lat"], 4), round(destination["lng"], 4))
        )
        if same_text or same_point:
            raise serializers.ValidationError({"destination": ["Destination must be different from the origin."]})
        return attrs


class TripPlanSerializer(serializers.ModelSerializer):
    """Read shape: inputs under `input`, computed result fields at the top level."""

    class Meta:
        model = TripPlan
        fields = ["id", "created_at", "origin", "destination", "departure_at", "load_weight_lb", "interval_miles"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {
            "id": data.pop("id"),
            "created_at": data.pop("created_at"),
            "input": data,
            **instance.result,
        }


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=3, max_length=PLACE_TEXT_MAX, trim_whitespace=True)
