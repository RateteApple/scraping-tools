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

    async def open_browser(
        self,
        debug: bool = False,
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
        start = time.time()
        self.driver = webdriver.Chrome(options)
        end = time.time()
        if debug:
            logger.debug(f"launch browser: {end - start} sec")
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
        # セクション毎の作品リストを取得(CSSselector: div#search_result_list > ul > li)
        on_sale_work_elms: list[WebElement] = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div#search_result_list > ul > li"))
        )

        # 作品リストを取得
        async def get_on_sale_works(elms) -> list[dict]:
            works = []
            tasks = [asyncio.create_task(process_elm(elm)) for elm in elms]
            for task in asyncio.as_completed(tasks):
                works.append(await task)

            return works

        async def process_elm(elm: WebElement) -> dict:
            try:
                title = elm.find_element(
                    By.CSS_SELECTOR,
                    ".work_name a",
                ).text

                url = elm.find_element(
                    By.CSS_SELECTOR,
                    ".work_name a",
                ).get_attribute("href")

                id = url.split("/")[-1].split(".")[0].replace(".html", "")

                discount: bool = True if elm.find_elements(By.CSS_SELECTOR, ".work_price.discount") else False
                if discount:
                    base_price = (
                        elm.find_element(
                            By.CSS_SELECTOR,
                            ".strike",
                        )
                        .text.replace("円", "")
                        .replace(",", "")
                    )
                    discount_price = (
                        elm.find_element(
                            By.CSS_SELECTOR,
                            ".work_price.discount",
                        )
                        .text.replace("円", "")
                        .replace(",", "")
                    )
                else:
                    base_price = (
                        elm.find_element(
                            By.CSS_SELECTOR,
                            ".work_price",
                        )
                        .text.replace("円", "")
                        .replace(",", "")
                    )
                    discount_price = None

                sale_count = elm.find_element(
                    By.CSS_SELECTOR,
                    ".work_dl span",
                ).text.replace(",", "")

                category = elm.find_element(
                    By.CSS_SELECTOR,
                    ".work_category",
                ).text

                work = {
                    "title": title,
                    "url": url,
                    "id": id,
                    "base_price": base_price,
                    "discount_price": discount_price,
                    "sale_count": sale_count,
                    "category": category,
                }
            except NoSuchElementException as e:
                logger.warning(e)
            else:
                return work

        works = await get_on_sale_works(on_sale_work_elms)

        # サークル情報を追加
        for work in works:
            work["circle"] = {
                "id": self.id,
                "url": self.url,
                "name": self.driver.find_element(By.CSS_SELECTOR, "span.original_name").text,
            }

        return works


async def main():
    circle = Circle("RG46817")
    await circle.open_browser(debug=True)
    works = await circle.get_works_by_selenium()
    pprint(works)


if __name__ == "__main__":
    coloredlogs.install(level="DEBUG", logger=logger)
    asyncio.run(main())
