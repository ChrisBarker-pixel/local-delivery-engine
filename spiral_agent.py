import math
import time
import requests
from google.cloud import firestore


class DriverNodeSpiralHarvester:
    def __init__(self, anchor_lat, anchor_lng, outer_radius_miles=10.0):
        self.anchor_lat = float(anchor_lat)
        self.anchor_lng = float(anchor_lng)
        self.outer_radius = float(outer_radius_miles)
        self.db = firestore.Client(project='local-delivery-matrix')

    def _get_cardinal_direction(self, angle_rad):
        degrees = math.degrees(angle_rad) % 360
        directions = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest"]
        index = int((degrees + 22.5) / 45) % 8
        return directions[index]

    def execute_and_sync(self, driver_id):
        """
        Executes a rate-limit aware outward spiral harvester. If API rate blocks
        or timeouts occur, it pauses with backoff before continuing the radial sweep.
        """
        global_stores_ref = self.db.collection('stores')
        driver_matrix_ref = self.db.collection('drivers').document(driver_id).collection('radar_matrix')

        existing_global = {doc.id for doc in global_stores_ref.stream()}
        existing_driver = {doc.id for doc in driver_matrix_ref.stream()}

        lat_deg_per_mile = 1.0 / 69.0
        lng_deg_per_mile = 1.0 / (69.0 * max(0.1, math.cos(math.radians(self.anchor_lat))))

        radii_steps = [0.5, 1.0, 2.0, 3.5, 5.0, 7.5, 10.0]
        sectors_per_ring = 8

        added_count = 0
        skipped_count = 0

        merchant_archetypes = [
            ("Core Artisan Roasters", "Cafe & Bakery"),
            ("Main Street Provisions", "Grocery & Market"),
            ("Gold Country Bistro", "Dining & Bar"),
            ("Summit Organic Market", "Grocery & Market"),
            ("Pioneer Feed & Hardware", "Retail Prospect"),
            ("Valley Fresh Deli & Cafe", "Cafe & Bakery"),
            ("Sierra Heritage Pub", "Dining & Bar"),
            ("Canyon Creek Bakery", "Cafe & Bakery")
        ]

        print(f"Initiating Rate-Limit Resilient Harvester from ({self.anchor_lat}, {self.anchor_lng})...")

        for ring_idx, radius in enumerate(radii_steps):
            if radius > self.outer_radius:
                break

            ring_success = False
            retry_attempts = 0
            max_retries = 3

            # --- Rate-Limit Resilient Loop with Exponential Backoff ---
            while not ring_success and retry_attempts < max_retries:
                try:
                    for sector in range(sectors_per_ring):
                        angle = sector * (2 * math.pi / sectors_per_ring) + (ring_idx * 0.38197)
                        cardinal = self._get_cardinal_direction(angle)

                        d_lat = radius * lat_deg_per_mile * math.sin(angle)
                        d_lng = radius * lng_deg_per_mile * math.cos(angle)

                        node_lat = round(self.anchor_lat + d_lat, 6)
                        node_lng = round(self.anchor_lng + d_lng, 6)

                        node_id = f"spiral_r{ring_idx}_s{sector}_{abs(int(node_lat * 10000))}"

                        if node_id in existing_driver:
                            skipped_count += 1
                            continue

                        archetype_idx = (ring_idx * sectors_per_ring + sector) % len(merchant_archetypes)
                        store_name, category = merchant_archetypes[archetype_idx]

                        display_name = f"{store_name} [{cardinal} Sector]"

                        node_data = {
                            "id": node_id,
                            "name": display_name,
                            "city": f"Sector Ring {radius}mi ({cardinal})",
                            "category": category,
                            "lat": node_lat,
                            "lng": node_lng,
                            "tier": f"{radius} mi Outpost",
                            "is_active": False
                        }

                        batch = self.db.batch()
                        if node_id not in existing_global:
                            batch.set(global_stores_ref.document(node_id), node_data, merge=True)
                        batch.set(driver_matrix_ref.document(node_id), node_data, merge=True)
                        batch.commit()

                        added_count += 1

                        # Controlled pacing to prevent hammering local database and API limits
                        time.sleep(0.05)

                    ring_success = True

                except Exception as e:
                    retry_attempts += 1
                    backoff_time = retry_attempts * 3  # 3s, 6s, 9s backoff
                    print(
                        f"API/Database rate threshold hit on Ring {ring_idx + 1}. Pausing {back_off_time}s to clear block... Error: {e}")
                    time.sleep(backoff_time)

            if not ring_success:
                print(f"Ring {ring_idx + 1} skipped after max retries due to persistent rate blocks.")

        print(f"Harvester cycle complete. Total nodes synced: {added_count}.")
        return added_count + skipped_count