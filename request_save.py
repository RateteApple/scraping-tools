import requests
import json
from bs4 import BeautifulSoup

url = ""

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

res = requests.get(url, headers=headers)

soup = BeautifulSoup(res.text, "html.parser")


# 保存
with open("test.html", mode="w", encoding="utf-8") as f:
    f.write(soup.prettify())
