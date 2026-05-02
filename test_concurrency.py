import threading
import requests

URL = "http://127.0.0.1:8000/api/orders/"
TOKEN ="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc3NzQ5OTUzLCJpYXQiOjE3Nzc3NDYzNTMsImp0aSI6IjI2YjUyODQwNWEzYjQ4Nzg5YzdjOGNkMmI0ZjJiNGViIiwidXNlcl9pZCI6MX0.aMQpvjDdPHC5YfOQS213iMOPimj12S_eKqXDH545Q0w"
print("URL is:", URL)
def order():
    try:
        response = requests.post(
            URL,
            json={
                "product_id": 1,
                "quantity": 1
            },
            headers={
                "Authorization": f"Bearer {TOKEN}"
            },
            timeout=30,
            proxies={"http": None, "https": None}
        )
        print(response.status_code, response.text)
    except Exception as e:
        print("Error:", e)

threads = []

for _ in range(3):
    t = threading.Thread(target=order)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

