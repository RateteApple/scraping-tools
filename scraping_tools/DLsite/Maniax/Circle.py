from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException

import asyncio
import time
import logging, coloredlogs
from pprint import pprint

from functools import wraps

logger = logging.getLogger(__name__)


class Circle:
    def __init__(self, id: str):
        # idの形式チェック
        if not id.startswith("RG"):
            raise ValueError("id must start with RG.")

        self.id = id
        self.url = f"https://www.dlsite.com/maniax/circle/profile/=/maker_id/{id}.html"

    def __getattr__(self, name: str):
        # ドライバを起動
        if name == "driver":
            self.open_browser()
            return self.driver

    def open_browser(
        self,
        driver: webdriver.Chrome = None,
        img_load: bool = False,
        gui: bool = False,
        timeout: int = 5,
    ) -> webdriver.Chrome:
        """ブラウザを開く"""
        # ブラウザのオプション
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")  # 保護機能を無効化
        options.add_argument("--disable-gpu")  # GPUの使用を無効化
        options.add_argument("--window-size=1920,1080")  # Windowサイズを1920x1080に設定
        options.add_experimental_option("excludeSwitches", ["enable-logging"])  # ログを無効化
        options.add_argument("--disable-extensions")  # 拡張機能を無効化
        if not img_load:
            options.add_argument("--blink-settings=imagesEnabled=false")  # 画像読み込みを無効化
        if not gui:
            options.add_argument("--headless")  # GUIを無効化

        # ブラウザを開く
        if not driver:
            self.driver = webdriver.Chrome(options)
        # 待機時間を設定
        self.timeout = timeout

        # Cookieの追加
        self.driver.get("https://www.dlsite.com")
        self.driver.add_cookie({"name": "adultchecked", "value": "1", "domain": ".dlsite.com"})

        return self.driver

    async def get_work(self) -> list:
        # ページを開く
        self.driver.get(self.url)
        logger.debug(f"open {self.url}")

        # セクション毎の作品リストを取得
        on_sale_work_elms: list[WebElement] = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div#search_result_list > ul > li"))
        )
        # TODO
        upcomming_work_elms: list[WebElement] = []

        # 作品リストを取得
        on_sale_works = await asyncio.gather(*[self._on_sale_works_elm(elm) for elm in on_sale_work_elms])
        upcomming_works = await asyncio.gather(*[self._upcomming_works_elm(elm) for elm in upcomming_work_elms])

        # 結合
        works = on_sale_works + upcomming_works

        return works

    async def _on_sale_works_elm(self, elm: WebElement) -> dict:
        """販売中の作品リストを取得"""

        async def get_title(elm: WebElement) -> str:
            try:
                title = elm.find_element(By.CSS_SELECTOR, ".work_name a").text
            except Exception as e:
                logger.error(f"failed to get title")
            else:
                return title

        async def get_url(elm: WebElement) -> str:
            try:
                url = elm.find_element(By.CSS_SELECTOR, ".work_name a").get_attribute("href")
            except Exception as e:
                logger.error(f"failed to get url")
            else:
                return url

        async def get_price(elm: WebElement) -> dict:
            try:
                discount: bool = True if elm.find_elements(By.CSS_SELECTOR, ".work_price.discount") else False
                if discount:
                    base_price = elm.find_element(By.CSS_SELECTOR, ".strike").text.replace("円", "").replace(",", "")
                    discount_price = elm.find_element(By.CSS_SELECTOR, ".work_price.discount").text.replace("円", "").replace(",", "")
                else:
                    base_price = elm.find_element(By.CSS_SELECTOR, ".work_price").text.replace("円", "").replace(",", "")
                    discount_price = None
            except Exception as e:
                logger.error(f"failed to get price")
            else:
                return {"base": base_price, "discount": discount_price}

        async def get_sale_count(elm: WebElement) -> int:
            try:
                sale_count = elm.find_element(By.CSS_SELECTOR, ".work_dl span").text.replace(",", "")
            except Exception as e:
                logger.error(f"failed to get sale_count")
            else:
                return sale_count

        async def get_category(elm: WebElement) -> str:
            try:
                category = elm.find_element(By.CSS_SELECTOR, ".work_category").text
            except Exception as e:
                logger.error(f"failed to get category")
            else:
                return category

        # 作品情報を取得
        tasks = [
            get_title(elm),
            get_url(elm),
            get_price(elm),
            get_sale_count(elm),
            get_category(elm),
        ]
        title, url, price, sale_count, category = await asyncio.gather(*tasks)
        work = {
            "title": title,
            "url": url,
            "price": price,
            "sale_count": sale_count,
            "category": category,
            "circle": {
                "id": self.id,
                "url": self.url,
                "name": self.driver.find_element(By.CSS_SELECTOR, "span.original_name").text,
            },
        }
        return work

    async def _upcomming_works_elm(self) -> list:
        # TODO
        return []


async def main():
    circle = Circle("RG42511")
    works = await circle.get_work()
    pprint(works)


if __name__ == "__main__":
    coloredlogs.install(level="DEBUG", logger=logger)
    asyncio.run(main())
