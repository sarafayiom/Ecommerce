from queue import Empty, Queue
from locust import HttpUser, between, task
#هون استخدمت الطابور مشان اضمن انو كل مستخدم وهمي عم ياخد حساب حقيقي وفريد 
user_queue = Queue()
for i in range(1, 100):
    user_queue.put((f"user_clean100_{i}", "testpass123"))

class EcommerceUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.token = None
        self.headers = {}

        try:
            username, password = user_queue.get_nowait()
        except Empty:
            print("انتهت الحسابات المتاحة في الطابور!")
            return

        with self.client.post(
            "/api/login/",
            json={"username": username, "password": password},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                self.token = response.json().get("access")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                response.success()
            else:
                response.failure(f" فشل تسجيل دخول {username}: كود {response.status_code}")

    @task(3)
    def products(self):
        if self.token:
            self.client.get("/api/products/", headers=self.headers)

    @task(2)
    def top_products(self):
        if self.token:
            self.client.get("/api/top-products/", headers=self.headers)

    @task(2)
    def checkout(self):
        if self.token:
            self.client.post(
                "/api/checkout/",
                json={"product_id": 1, "quantity": 1},
                headers=self.headers,
            )

    @task(1)
    def create_order(self):
        if self.token:
            self.client.post(
                "/api/orders/",
                json={"product_id": 1, "quantity": 1},
                headers=self.headers,
            )