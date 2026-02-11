import os
import math
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Station


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


class RouteView(APIView):
    """POST start,end -> returns route geometry + recommended fuel stops + cost
    Environment: set ORS_API_KEY
    """

    def post(self, request):
        start = request.data.get('start')
        end = request.data.get('end')
        if not start or not end:
            return Response({'detail': 'start and end required'}, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.environ.get('ORS_API_KEY')
        if not api_key:
            return Response({'detail': 'ORS_API_KEY not set'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # OpenRouteService directions (one call, geojson output)
        url = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson'

        # ORS expects coordinates, so geocode start/end first
        geocode_url = 'https://api.openrouteservice.org/geocode/search'
        def geocode(address):
            r = requests.get(
                geocode_url,
                params={'api_key': api_key, 'text': address, 'size': 1, 'boundary.country': 'US,CA'},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            features = data.get('features')
            if not features:
                return None
            coords = features[0]['geometry']['coordinates']
            return coords[1], coords[0]

        try:
            s_latlon = geocode(start)
            e_latlon = geocode(end)
        except Exception as exc:
            return Response({'detail': 'geocoding error', 'error': str(exc)}, status=500)

        if not s_latlon or not e_latlon:
            return Response({'detail': 'could not geocode start or end'}, status=400)

        # ORS directions require POST with coordinates
        coords = [[s_latlon[1], s_latlon[0]], [e_latlon[1], e_latlon[0]]]
        try:
            r = requests.post(
                url,
                json={'coordinates': coords},
                headers={'Authorization': api_key, 'Content-Type': 'application/json'},
                timeout=20,
            )
            r.raise_for_status()
            route = r.json()
        except Exception as exc:
            return Response({'detail': 'directions error', 'error': str(exc)}, status=500)

        # Extract distance (meters) and geometry coords
        features = route.get('features') or []
        if not features and route.get('routes'):
            return Response(
                {
                    'detail': 'route format is not geojson; check ORS endpoint',
                    'route': route,
                },
                status=502,
            )
        if not features:
            return Response({'detail': 'no route found', 'route': route}, status=502)

        feature = features[0] or {}
        summary = (feature.get('properties') or {}).get('summary') or {}
        distance_m = summary.get('distance')
        geometry = feature.get('geometry') or {}

        # Fuel planning: sample along the route and choose cheapest nearby stations
        max_range_miles = 500
        miles_per_gallon = 10
        total_miles = distance_m / 1609.344 if distance_m else 0
        if total_miles == 0:
            return Response({'detail': 'zero-distance route', 'route': route})

        num_legs = math.ceil(total_miles / max_range_miles)
        # compute fraction positions along route
        fractions = [i / num_legs for i in range(1, num_legs + 1)]

        # For simplicity, decode geometry coordinates list
        coords_list = geometry.get('coordinates') or []
        if not coords_list:
            return Response({'detail': 'route has no geometry', 'route': route}, status=502)

        def point_at_fraction(frac):
            # linear interpolation along coordinate points
            if not coords_list:
                return None
            idx = int(frac * (len(coords_list) - 1))
            lon, lat = coords_list[idx]
            return lat, lon

        # load stations with coords
        stations = list(Station.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True))

        selected_stops = []
        total_cost = 0.0

        for frac in fractions:
            pt = point_at_fraction(frac)
            if not pt:
                continue
            lat, lon = pt
            # find stations within 100 km
            candidates = []
            for s in stations:
                d_km = haversine(lat, lon, s.latitude, s.longitude)
                if d_km <= 160:  # ~100 miles
                    candidates.append((d_km, s))
            if not candidates:
                continue
            # pick cheapest
            candidates.sort(key=lambda x: x[1].price)
            chosen = candidates[0][1]
            selected_stops.append({
                'id': chosen.id,
                'name': chosen.name,
                'city': chosen.city,
                'state': chosen.state,
                'price': chosen.price,
                'latitude': chosen.latitude,
                'longitude': chosen.longitude,
            })
        # Estimate cost: total gallons needed = total_miles / mpg
        gallons_needed = total_miles / miles_per_gallon
        if selected_stops:
            avg_price = sum([s['price'] for s in selected_stops]) / len(selected_stops)
            total_cost = gallons_needed * avg_price

        return Response({
            'route': {
                'distance_m': distance_m,
                'geometry': geometry,
            },
            'stops': selected_stops,
            'estimated_total_cost': round(total_cost, 2),
            'gallons_needed': round(gallons_needed, 2),
        })
