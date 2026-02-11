from django.db import models


class Station(models.Model):
    opis_id = models.CharField(max_length=32, blank=True, null=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=512, blank=True, null=True)
    city = models.CharField(max_length=128, blank=True, null=True)
    state = models.CharField(max_length=64, blank=True, null=True)
    rack_id = models.CharField(max_length=64, blank=True, null=True)
    price = models.FloatField()
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) - {self.price}"
