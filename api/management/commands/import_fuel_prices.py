import csv
import os
import time
from pathlib import Path

import requests
from django.core.management.base import BaseCommand
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from api.models import Station


class Command(BaseCommand):
    help = 'Import stations from CSV and geocode them (adds latitude/longitude)'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of rows to process (0 = all)')

    def handle(self, *args, **options):
        path = options['csv_path']
        limit = int(options.get('limit', 0))

        geolocator = Nominatim(user_agent='fuel-assessment', timeout=10)
        geocode = RateLimiter(
            geolocator.geocode,
            min_delay_seconds=1.2,
            max_retries=2,
            error_wait_seconds=5,
            swallow_exceptions=True,
            return_value_on_exception=None,
        )

        ors_api_key = os.environ.get('ORS_API_KEY')

        def geocode_ors(query):
            if not ors_api_key:
                return None
            url = 'https://api.openrouteservice.org/geocode/search'
            params = {
                'api_key': ors_api_key,
                'text': query,
                'size': 1,
                'boundary.country': 'US,CA',
            }
            try:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                return None
            features = data.get('features') or []
            if not features:
                return None
            feature = features[0]
            coords = (feature.get('geometry') or {}).get('coordinates') or []
            if len(coords) != 2:
                return None
            props = feature.get('properties') or {}
            country_code = (props.get('country_code') or '').lower()
            return coords[1], coords[0], country_code

        def clean(s):
            if not s:
                return ''
            return ' '.join(s.replace('\n', ' ').replace('\t', ' ').strip().split())

        failed_path = Path('failed_geocodes.csv')
        if not failed_path.exists():
            with open(failed_path, 'w', newline='', encoding='utf-8') as ffail:
                w = csv.writer(ffail)
                w.writerow(['OPIS Truckstop ID', 'Truckstop Name', 'Query', 'Reason'])

        row_index = 0
        processed = 0
        saved_count = 0
        skipped = 0
        failed_count = 0

        with open(path, newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                row_index += 1
                if limit and processed >= limit:
                    break

                name = row.get('Truckstop Name')
                city = row.get('City')
                state = row.get('State')
                address = row.get('Address')
                opis = row.get('OPIS Truckstop ID')
                price = row.get('Retail Price')
                rack = row.get('Rack ID')

                try:
                    price_f = float(price)
                except Exception:
                    continue

                station, created = Station.objects.get_or_create(
                    opis_id=opis,
                    name=name,
                    defaults={
                        'address': address,
                        'city': city,
                        'state': state,
                        'rack_id': rack,
                        'price': price_f,
                    }
                )

                if station.latitude and station.longitude:
                    skipped += 1
                    processed += 1
                    if processed % 100 == 0:
                        self.stdout.write(
                            f"Progress: processed={processed}, saved={saved_count}, skipped={skipped}, failed={failed_count}"
                        )
                    continue

                addr = clean(address)
                c = clean(city)
                st = clean(state)

                attempts = []
                if addr:
                    attempts.append(f"{addr}, {c}, {st}")
                    attempts.append(f"{addr}, {st}")
                if name:
                    attempts.append(f"{name}, {c}, {st}")
                if c and st:
                    attempts.append(f"{c}, {st}")
                if st:
                    attempts.append(st)
                if opis:
                    attempts.append(f"OPIS {opis} {c} {st}")

                lat = None
                lon = None
                used_query = None

                for q in attempts:
                    if not q or q.strip() == ',':
                        continue

                    ors_result = geocode_ors(q)
                    if ors_result:
                        lat, lon, country_code = ors_result
                        if country_code and country_code not in ('us', 'ca'):
                            lat = None
                            lon = None
                        else:
                            used_query = q
                            break

                    try:
                        loc = geocode(q, addressdetails=True)
                    except Exception as exc:
                        self.stdout.write(f"Geocode error for {q}: {exc}")
                        time.sleep(1)
                        continue

                    if loc:
                        try:
                            country_code = (loc.raw.get('address') or {}).get('country_code')
                        except Exception:
                            country_code = None
                        if country_code and country_code.lower() not in ('us', 'ca'):
                            continue
                        lat = loc.latitude
                        lon = loc.longitude
                        used_query = q
                        break

                if lat is not None and lon is not None:
                    station.latitude = lat
                    station.longitude = lon
                    station.save()
                    saved_count += 1
                    processed += 1
                    self.stdout.write(f"Saved {station} -> {lat},{lon} (query: {used_query})")
                else:
                    failed_count += 1
                    processed += 1
                    qlog = attempts[0] if attempts else ''
                    self.stdout.write(f"No geocode for {qlog}")
                    with open(failed_path, 'a', newline='', encoding='utf-8') as ffail:
                        w = csv.writer(ffail)
                        w.writerow([opis, name, qlog, 'no_result'])

                if processed % 100 == 0:
                    self.stdout.write(
                        f"Progress: processed={processed}, saved={saved_count}, skipped={skipped}, failed={failed_count}"
                    )

        self.stdout.write("\nImport summary:")
        self.stdout.write(f"Total rows read: {row_index}")
        self.stdout.write(f"Rows processed: {processed}")
        self.stdout.write(f"Saved (new geocodes): {saved_count}")
        self.stdout.write(f"Skipped (existing coordinates): {skipped}")
        self.stdout.write(f"Failed geocodes: {failed_count}")
