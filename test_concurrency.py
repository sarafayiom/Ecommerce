import threading
import requests

URL = "http://127.0.0.1:8000/api/orders/"
TOKEN ="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgxNDczODg2LCJpYXQiOjE3ODE0NzAyODYsImp0aSI6IjkxNjVhYWRlMzQzODRlY2ZiZTU0ODIxNGNiNGMzNDg1IiwidXNlcl9pZCI6IjEifQ.7rAZLZaH7d_465sR318QsuAXA0KY_Vwu9wbPnH12hNE"
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

for _ in range(20):
    t = threading.Thread(target=order)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

