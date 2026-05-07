import requests

try:
    resp = requests.post("http://localhost:8000/chat", json={
        "messages": [{"role": "user", "content": "What is machine learning?"}],
        "model": "gemma2"
    })
    print(resp.status_code)
    print(resp.json())
except Exception as e:
    print(e)
