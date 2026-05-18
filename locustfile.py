from locust import HttpUser, task, between

VALID_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc5MTEzNjc0LCJpYXQiOjE3NzkxMTAwNzQsImp0aSI6IjZjMzBkNjJlNWEwOTQzMmZiNzIwYThmNzUwYjU2NzdiIiwidXNlcl9pZCI6IjMifQ.gzI5tXy6X_lil1_GTSiihMDSSJHA4XV7H7qnSWIx_L0"

class OrderTestUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        self.user_token = VALID_TOKEN

    @task
    def create_order(self):
        headers = {
            'Authorization': f'Bearer {self.user_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "product_id": 1, 
            "quantity": 1
        }

        with self.client.post(
            "/api/orders/", 
            json=payload, 
            headers=headers, 
            name="POST /api/orders/ (Order Creation)",
            catch_response=True
        ) as response:
            if response.status_code in [201, 202]:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}, Error: {response.text}")