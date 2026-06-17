from locust import HttpUser, task, between

class CachePerformanceTest(HttpUser):
    wait_time = between(1, 2)

    @task
    def get_products(self):
        self.client.get("/api/products/", name="GET /products")

    @task
    def get_top10(self):
        self.client.get("/api/top-products/", name="GET /top-products")

    @task
    def get_product_details(self):
        self.client.get("/api/products/1/", name="GET /products/1")
