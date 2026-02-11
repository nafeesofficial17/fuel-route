from rest_framework import serializers
from .models import Station


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = ['id', 'opis_id', 'name', 'address', 'city', 'state', 'rack_id', 'price', 'latitude', 'longitude']
