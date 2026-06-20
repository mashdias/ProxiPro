import requests
import traceback
import sys

try:
    print("Sending POST request to localhost:8000")
    res = requests.post("http://127.0.0.1:8000/api/auth/google", json={"token": "testtoken123"}, timeout=5)
    print(res.status_code)
    print(res.text)
except Exception as e:
    print("Error occurred:")
    traceback.print_exc()
