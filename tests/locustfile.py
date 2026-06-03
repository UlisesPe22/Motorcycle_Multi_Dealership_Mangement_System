"""
Locust load-test scenarios for the Moto Dealer API.

Run:
    locust -f tests/locustfile.py --host http://localhost:8000

Before running GeminiPipelineUser tasks, place real test files in:
    tests/test_files/
    (see tests/test_files/README.md for the list)

Dealership IDs and model IDs below are set after running seed_load_test.py.
To confirm: GET /reservations/dealerships and GET /reservations/models.
"""

import os
import random
from locust import HttpUser, task, between, constant
BASE_URL = "http://localhost:8000"
TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), "test_daa")

# Populated by seed_load_test.py — queried from DB by name
DEALERSHIP_VIA_MORELOS_ID = 1       # PLACEHOLDER — replace with actual ID after querying DB
DEALERSHIP_IGNACIO_ZARAGOZA_ID = 2  # PLACEHOLDER — replace with actual ID after querying DB
EMPLOYEE_USER_ID = 2
MODEL_IDS = list(range(1, 11))      # PLACEHOLDER — replace with actual model IDs
CLIENT_IDS = list(range(1, 201))    # 200 seeded clients


# ======================================================================== #
# Scenario 1 — InventoryUser                                                #
# Simulates vendors browsing inventory with different filter combinations.   #
# 50 users, weight=5.                                                        #
# ======================================================================== #

class InventoryUser(HttpUser):
    weight = 5
    wait_time = between(1, 3)

    @task(3)
    def browse_all(self):
        self.client.get("/motorcycles/")

    @task(2)
    def browse_via_morelos(self):
        self.client.get(f"/motorcycles/?dealership_id={DEALERSHIP_VIA_MORELOS_ID}")

    @task(2)
    def browse_ignacio_zaragoza(self):
        self.client.get(f"/motorcycles/?dealership_id={DEALERSHIP_IGNACIO_ZARAGOZA_ID}")

    @task(2)
    def browse_available(self):
        self.client.get("/motorcycles/?status=available")

    @task(1)
    def browse_by_model(self):
        self.client.get(f"/motorcycles/?model_id={random.choice(MODEL_IDS)}")

    @task(1)
    def browse_available_via_morelos(self):
        self.client.get(
            f"/motorcycles/?status=available&dealership_id={DEALERSHIP_VIA_MORELOS_ID}"
        )

    @task(2)
    def list_clients(self):
        self.client.get("/clients/")

    @task(1)
    def list_reservation_clients(self):
        self.client.get("/reservations/clients")


# ======================================================================== #
# Scenario 2 — ReservationUser                                              #
# Simulates vendors creating reservations.                                   #
# 20 users, weight=2.                                                        #
# ======================================================================== #
class ReservationUser(HttpUser):
    weight = 2
    wait_time = between(2, 5)

    model_color_map = {}

    def on_start(self):
        if not ReservationUser.model_color_map:
            resp = self.client.get("/reservations/models")
            if resp.status_code == 200:
                for m in resp.json():
                    if m["colors"]:
                        ReservationUser.model_color_map[m["model_id"]] = m["colors"]

    def _random_model_and_color(self):
        if not self.model_color_map:
            return random.choice(MODEL_IDS), ["Rojo"]
        model_id = random.choice(list(self.model_color_map.keys()))
        color = random.choice(self.model_color_map[model_id])
        return model_id, [color]

    @task
    def preflight_and_create(self):
        self.client.get("/reservations/clients")
        self.client.get("/reservations/models")
        self.client.get("/reservations/dealerships")
        model_id, colors = self._random_model_and_color()
        self.client.post(
            "/reservations/create",
            json={
                "client_id":      random.choice(CLIENT_IDS),
                "model_id":       model_id,
                "dealership_id":  random.choice(
                    [DEALERSHIP_VIA_MORELOS_ID, DEALERSHIP_IGNACIO_ZARAGOZA_ID]
                ),
                "deposit_amount": round(random.uniform(2000, 8000), 2),
                "colors":         colors,
            },
        )


class MixedTrafficUser(HttpUser):
    weight = 3
    wait_time = between(1, 4)

    model_color_map = {}

    def on_start(self):
        if not MixedTrafficUser.model_color_map:
            resp = self.client.get("/reservations/models")
            if resp.status_code == 200:
                for m in resp.json():
                    if m["colors"]:
                        MixedTrafficUser.model_color_map[m["model_id"]] = m["colors"]

    def _random_model_and_color(self):
        if not self.model_color_map:
            return random.choice(MODEL_IDS), ["Rojo"]
        model_id = random.choice(list(self.model_color_map.keys()))
        color = random.choice(self.model_color_map[model_id])
        return model_id, [color]

    @task(7)
    def browse_inventory(self):
        suffix = random.choice([
            "",
            f"?dealership_id={DEALERSHIP_VIA_MORELOS_ID}",
            f"?dealership_id={DEALERSHIP_IGNACIO_ZARAGOZA_ID}",
            "?status=available",
            f"?model_id={random.choice(MODEL_IDS)}",
        ])
        self.client.get(f"/motorcycles/{suffix}")

    @task(2)
    def create_reservation(self):
        model_id, colors = self._random_model_and_color()
        self.client.post(
            "/reservations/create",
            json={
                "client_id":      random.choice(CLIENT_IDS),
                "model_id":       model_id,
                "dealership_id":  random.choice(
                    [DEALERSHIP_VIA_MORELOS_ID, DEALERSHIP_IGNACIO_ZARAGOZA_ID]
                ),
                "deposit_amount": round(random.uniform(2000, 8000), 2),
                "colors":         colors,
            },
        )

    @task(1)
    def lookup_clients(self):
        self.client.get("/clients/")

# ======================================================================== #
# Scenario 4 — GeminiPipelineUser                                           #
# Sequential Gemini pipeline calls — each user specialises in one pipeline. #
# 3 users, weight=1.                                                         #
# ======================================================================== #
# class GeminiPipelineUser(HttpUser):
    weight = 1
    wait_time = constant(999999)  # fires @task only once effectively

    _sequence_done = False

    def on_start(self):
        # Only the first spawned GeminiPipelineUser runs the full sequence
        if GeminiPipelineUser._sequence_done:
            return
        GeminiPipelineUser._sequence_done = True

        # Step 1 — Client registration
        self._register_client()

        # Step 2 — Purchase order (must come before order confirmation)
        self._upload_purchase_order()

        # Step 3 — Order confirmation (orden de traslado, depends on purchase order)
        self._upload_order_confirmation()

        # Step 4 — Delivery confirmation (depends on order confirmation)
        self._upload_delivery()

    @task
    def idle(self):
        pass  # never really fires due to wait_time = constant(999999)

    def _register_client(self):
        ine_front = os.path.join(TEST_FILES_DIR, "sub1.jpeg")
        ine_back  = os.path.join(TEST_FILES_DIR, "sub2.jpeg")
        if not os.path.exists(ine_front) or not os.path.exists(ine_back):
            print("[GeminiPipelineUser] INE files not found — skipping client registration")
            return
        with open(ine_front, "rb") as f_front, open(ine_back, "rb") as f_back:
            resp = self.client.post(
                "/clients/register",
                files={
                    "front_file": ("ine_front.jpg", f_front, "image/jpeg"),
                    "back_file":  ("ine_back.jpg",  f_back,  "image/jpeg"),
                },
                data={
                    "email": f"loadtest_{random.randint(1000, 9999)}@test.com",
                    "phone": f"55{random.randint(10000000, 99999999)}",
                },
                timeout=120,
            )
        print(f"[GeminiPipelineUser] client_reg → {resp.status_code}")

    def _upload_purchase_order(self):
        pdf_path = os.path.join(TEST_FILES_DIR, "OrdenCompra_TLAL_11_motos.pdf")
        if not os.path.exists(pdf_path):
            print("[GeminiPipelineUser] Purchase order PDF not found — skipping")
            return
        resp = self.client.post(
            "/events/",
            params={"event_type_name": "purchase_order"},
        )
        if resp.status_code != 200:
            print(f"[GeminiPipelineUser] purchase_order event creation failed → {resp.status_code}")
            return
        submissions = resp.json().get("submissions", [])
        target = next(
            (s for s in submissions if s.get("slot_name") == "purchase_order_table"),
            submissions[0] if submissions else None,
        )
        if not target:
            print("[GeminiPipelineUser] No submission found for purchase_order_table")
            return
        submission_id = target["submission_id"]
        with open(pdf_path, "rb") as f:
            resp = self.client.post(
                f"/submissions/{submission_id}/upload",
                files={"file": ("orden_compra.pdf", f, "application/pdf")},
                timeout=120,
            )
        print(f"[GeminiPipelineUser] purchase_order upload → {resp.status_code}")

    def _upload_order_confirmation(self):
        pdf_path = os.path.join(TEST_FILES_DIR, "OrdenTraslado1_TLAL_11_motos.pdf")
        if not os.path.exists(pdf_path):
            print("[GeminiPipelineUser] Order confirmation PDF not found — skipping")
            return
        resp = self.client.post(
            "/events/",
            params={"event_type_name": "order_confirmation"},
        )
        if resp.status_code != 200:
            print(f"[GeminiPipelineUser] order_confirmation event creation failed → {resp.status_code}")
            return
        submissions = resp.json().get("submissions", [])
        target = next(
            (s for s in submissions if s.get("slot_name") == "order_table"),
            submissions[0] if submissions else None,
        )
        if not target:
            print("[GeminiPipelineUser] No submission found for order_table")
            return
        submission_id = target["submission_id"]
        with open(pdf_path, "rb") as f:
            resp = self.client.post(
                f"/submissions/{submission_id}/upload",
                files={"file": ("orden_confirmacion.pdf", f, "application/pdf")},
                timeout=120,
            )
        print(f"[GeminiPipelineUser] order_confirmation upload → {resp.status_code}")

    def _upload_delivery(self):
        pdf_path = os.path.join(TEST_FILES_DIR, "Entrega_TLAL_10_motos.pdf")
        if not os.path.exists(pdf_path):
            print("[GeminiPipelineUser] Delivery PDF not found — skipping")
            return
        with open(pdf_path, "rb") as f:
            resp = self.client.post(
                "/delivery-confirmations/upload",
                files={"file": ("entrega.pdf", f, "application/pdf")},
                data={
                    "declared_count": "10",
                    "dealership_id":  str(DEALERSHIP_VIA_MORELOS_ID),
                },
                timeout=120,
            )
        print(f"[GeminiPipelineUser] delivery upload → {resp.status_code}")