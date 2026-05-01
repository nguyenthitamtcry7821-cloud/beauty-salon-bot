from pyngrok import ngrok
import time

url = ngrok.connect(8000).public_url
print(f"\n ССЫЛКА: {url} \n")

while True:
    time.sleep(1)