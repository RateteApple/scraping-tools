from typing import Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException

import asyncio
import json
import time
import logging, coloredlogs
from pprint import pprint, pformat

from functools import wraps

import urllib.parse

logger = logging.getLogger(__name__)


class Work:
    """DLsiteの作品を扱うクラス"""

    work_type_dict = {
        "illust": "CG・イラスト",
        "movie": "動画",
        "audio": "ボイス・ASMR",
        "music": "音楽",
    }

    def __getattr__(self, name: str) -> Any:
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

    # ここからURL作成用のメソッド - - - - - - - - - - - - - - - - -
    @staticmethod
    async def gen_status(
        all: bool = False,
        on_sale: bool = False,
        preorder: bool = False,
        upcoming: bool = False,
    ) -> str:
        """ステータスを生成する"""

        # 複数の引数にTrueが指定されていないかチェック
        if sum([all, on_sale, preorder, upcoming]) != 1:
            raise ValueError("can't set multiple status to True.")

        if all:
            status = "all"
        elif on_sale:
            status = "on_sale"
        elif preorder:
            status = "preorder"
        elif upcoming:
            status = "upcoming"

        return status

    @staticmethod
    async def gen_keyword(
        and_: list = None,
        or_: list = None,
        not_: list = None,
        exact: list = None,
    ) -> str:
        """検索キーワードを生成する"""
        keyword = ""
        # and検索は単語をスペースで区切る
        if and_:
            keyword += " ".join(and_)
        # or検索は"パイプ(|)"で区切る
        if or_:
            keyword += "|" + "|".join(or_)
        # not検索は単語の前に"-"をつける
        if not_:
            keyword += " -" + " -".join(not_)
        # 完全一致検索は単語をダブルクォーテーションで囲む(AND検索でしか使えない)
        if exact:
            keyword += ' "' + '" "'.join(exact) + '"'
        return keyword

    @staticmethod
    async def gen_work_type(
        cg_illust: bool = False,
        video: bool = False,
        voice_asmr: bool = False,
        music: bool = False,
    ) -> dict[str, bool]:
        """作品形式を生成する"""
        work_type = {
            "illust": cg_illust,
            "movie": video,
            "audio": voice_asmr,
            "music": music,
        }
        return work_type

    @staticmethod
    async def gen_AI_option(
        *,
        hide_AI_generate: bool = False,
        hide_AI_use: bool = False,
    ) -> dict[str, bool]:
        """AIオプションを生成する"""
        AI_option = {
            "hide_AI_generate": hide_AI_generate,
            "hide_AI_use": hide_AI_use,
        }
        return AI_option

    @staticmethod
    async def gen_order(
        trend: bool = False,
        new: bool = False,
        old: bool = False,
        sale: bool = False,
        cheap: bool = False,
        expensive: bool = False,
        rate: bool = False,
        review: bool = False,
    ) -> str:
        """並び順を生成する

        Note:
            引数とURLパラメータで指定する値の対応は以下の通り
            人気順 : trend -> trend
            新着順 : new -> release_d
            古い順 : old -> release
            販売数順 : sale -> dl_d
            安い順 : cheap -> price
            高い順 : expensive -> price_d
            評価順 : rate -> rate_d
            レビュー数順 : review -> review_d
        """

        # 複数の引数にTrueが指定されていないかチェック
        if sum([trend, new, old, sale, cheap, expensive, rate, review]) != 1:
            raise ValueError("can't set multiple order to True.")

        if trend:
            order = "trend"
        elif new:
            order = "release_d"
        elif old:
            order = "release"
        elif sale:
            order = "dl_d"
        elif cheap:
            order = "price"
        elif expensive:
            order = "price_d"
        elif rate:
            order = "rate_d"
        elif review:
            order = "review_d"

        return order

    @staticmethod
    async def gen_url(
        *,
        status: str = None,
        work_type: dict = None,
        keyword: str = None,
        keyword_creater: str = None,
        order: str = None,
        per_page: int = None,
        page: int = None,
        show_type: str = None,
        AI_option: dict = None,
        language: str = "jp",
    ) -> list:
        """検索結果のURLを生成する

        Example:
            引数はWorkのクラスメソッドを使用して生成することができる。
            >>> url = await Work.gen_url(
                    status=await Work.gen_status(all=True),
                    work_type=await Work.gen_work_type(),
                    keyword=await Work.gen_keyword(),
                    keyword_creater="天知遥",
                    order=await Work.gen_order(new=True),
                    per_page=50,
                    page=1,
                    show_type="box",
                    AI_option=await Work.gen_AI_option(hide_AI_generate=True, hide_AI_use=True),
                )
            >>> print(url)
            >>> "https://www.dlsite.com/maniax/fsr/=/language/jp/ana_flg/all/keyword_creater/%E5%A4%A9%E7%9F%A5%E9%81%A5/order/release_d/per_page/50/page/1/show_type/0/options_and_or/and/options_not%5B0%5D/AIG/options_not%5B1%5D/AIP/"
        """

        # ステータス
        async def add_status() -> str:
            nonlocal status

            if not status:
                return "ana_flg/all/"
            elif status == "on_sale":  # 販売中
                return "ana_flg/on_sale/"
            elif status == "preorder":  # 予約中
                return "is_reserve/1/"
            elif status == "upcoming":  # 予告中
                return "ana_flg/on/"
            else:
                raise ValueError("invalid status. valid status is all, on_sale, preorder or upcoming.")

        # 作品形式
        async def add_work_type() -> str:
            nonlocal work_type

            if not work_type:
                return ""
            else:
                para = ""
                for i, (key, value) in enumerate(work_type.items()):
                    if not value:
                        continue
                    try:
                        para += f"work_type_category[{i}]/{key}/work_type_category_name[{i}]/{Work.work_type_dict[key]}/"
                    except Exception as e:
                        logger.error(f"invalid work_type. if you want to use custom work_type, please use gen_work_type().\n{e}")
                        break
            return para

        # キーワード
        async def add_keyword() -> str:
            nonlocal keyword

            if not keyword:
                return ""
            else:
                return f"keyword/{keyword}/"

        # 特定のキーワード(声優、ライター、イラストレーターなど)
        async def add_keyword_creater() -> str:
            nonlocal keyword_creater

            if not keyword_creater:
                return ""
            else:
                return f"keyword_creater/{keyword_creater}/"

        # 並び順
        async def add_order() -> str:
            nonlocal order

            if not order:
                return ""
            else:
                return f"order/{order}/"

        # 1ページあたりの作品数
        async def add_per_page() -> str:
            nonlocal per_page

            if not per_page:
                return ""
            elif per_page not in [30, 50, 100]:
                logger.warning("per_page must be 30, 50 or 100.")
                return ""
            else:
                return f"per_page/{per_page}/"

        # ページ数
        async def add_page() -> str:
            nonlocal page

            if not page:
                return ""
            else:
                return f"page/{page}/"

        # 作品表示形式
        async def add_show_type() -> str:
            nonlocal show_type

            if not show_type:
                return ""
            elif show_type == "box":
                return f"show_type/0/"
            elif show_type == "list":
                return f"show_type/1/"
            else:
                raise ValueError("show_type must be list or box.")

        # AIの非表示オプション
        async def add_AI_option() -> str:
            nonlocal AI_option

            if not AI_option:
                pass
            else:
                if AI_option["hide_AI_generate"] and AI_option["hide_AI_use"]:
                    return "options_and_or/and/options_not[0]/AIG/options_not[1]/AIP/"
                elif AI_option["hide_AI_generate"]:
                    return "options_not[0]/AIG/"
                elif AI_option["hide_AI_use"]:
                    return "options_not[0]/AIP/"

        # ベースのURL
        url = f"https://www.dlsite.com/maniax/fsr/=/language/{language}/"
        # 並行実行でパラメータを生成
        tasks = [
            add_status(),
            add_work_type(),
            add_keyword(),
            add_keyword_creater(),
            add_order(),
            add_per_page(),
            add_page(),
            add_show_type(),
            add_AI_option(),
        ]
        # パラメータを追加
        for task in await asyncio.gather(*tasks):
            # パラメータが空文字列でなければ追加
            if task:
                url += task
        logger.debug(f"generated url: {url}")

        # URLをエンコード
        decoded_url = urllib.parse.quote(url, safe=":/?&=+")

        return decoded_url

    # ここから検索結果を取得するメソッド - - - - - - - - - - - - -
    async def search(self, url: str) -> list:
        """検索結果を取得する"""
        # ブラウザを開く
        self.driver.get(url)

        # 作品リストを取得
        work_elms = WebDriverWait(self.driver, self.timeout).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.n_worklist > *")))

        # 各作品に対して並行で情報を取得する
        tasks = [asyncio.create_task(self._get_work_info(work_elm)) for work_elm in work_elms]
        works = await asyncio.gather(*tasks)
        logger.debug(f"{pformat(works)}")
        return works

    async def _get_work_info(self, work_elm: WebElement) -> dict:
        async def get_status() -> str:
            try:
                expected_date: list = work_elm.find_elements(By.CSS_SELECTOR, ".expected_date")
            except Exception as e:
                logger.error(f"can't get is_on_sale.")
                return ""
            else:
                if expected_date:
                    return "upcoming"
                else:
                    return "on_sale"

        async def get_work_title() -> str:
            try:
                title = work_elm.find_element(By.CSS_SELECTOR, ".work_name a").text
            except Exception as e:
                logger.error(f"can't get work title.")
                return ""
            else:
                return title

        async def get_work_url() -> str:
            try:
                url = work_elm.find_element(By.CSS_SELECTOR, ".work_name a").get_attribute("href")
            except Exception as e:
                logger.error(f"can't get work url.")
                return ""
            else:
                return url

        async def get_work_thumbnail() -> str:
            try:
                thumbnail = work_elm.find_element(By.CSS_SELECTOR, "img.lazy").get_attribute("src")
            except Exception as e:
                logger.error(f"can't get work thumbnail.")
                return ""
            else:
                return thumbnail

        async def get_work_type() -> str:
            try:
                work_type = work_elm.find_element(By.CSS_SELECTOR, ".work_category").text
            except Exception as e:
                logger.error(f"can't get work type.")
                return ""
            else:
                return work_type

        async def get_work_price() -> dict:
            try:
                discount = True if work_elm.find_elements(By.CSS_SELECTOR, ".work_price.discount") else False
                # 元の価格
                base_price: str = work_elm.find_element(By.CSS_SELECTOR, ".strike").text if discount else work_elm.find_element(By.CSS_SELECTOR, ".work_price").text
                base_price: int = int(base_price.replace("円", "").replace(",", ""))
                # 割引後の価格
                discount_price: str = work_elm.find_element(By.CSS_SELECTOR, ".work_price.discount").text if discount else None
                discount_price: int = int(discount_price.replace("円", "").replace(",", "")) if discount_price else None
            except Exception as e:
                logger.error(f"can't get work price.")
                return ""
            else:
                return {"base": base_price, "discount": discount_price}

        async def get_work_circle_info() -> dict:
            try:
                circle_name = work_elm.find_element(By.CSS_SELECTOR, ".maker_name a").text
                circle_url = work_elm.find_element(By.CSS_SELECTOR, ".maker_name a").get_attribute("href")
                circle_id = circle_url.split("/")[-1].split(".")[0].replace(".html", "")
            except Exception as e:
                logger.error(f"can't get work circle info.")
                return ""
            else:
                circle_info = {
                    "name": circle_name,
                    "url": circle_url,
                    "id": circle_id,
                }
                return circle_info

        # 販売中の作品のみ価格を取得
        status = await get_status()
        if status == "on_sale":
            title, url, thumbnail, work_type, price, circle_info = await asyncio.gather(
                get_work_title(),
                get_work_url(),
                get_work_thumbnail(),
                get_work_type(),
                get_work_price(),
                get_work_circle_info(),
            )
        else:
            title, url, thumbnail, work_type, circle_info = await asyncio.gather(
                get_work_title(),
                get_work_url(),
                get_work_thumbnail(),
                get_work_type(),
                get_work_circle_info(),
            )
            price = None

        # 作品IDを取得
        id = url.split("/")[-1].split(".")[0].replace(".html", "")

        return {
            "id": id,
            "title": title,
            "url": url,
            "thumbnail": thumbnail,
            "type": work_type,
            "price": price,
            "circle": circle_info,
            "status": status,
        }


async def main():
    # url = await Work.gen_url(
    #     status=await Work.gen_status(on_sale=True),
    #     work_type=await Work.gen_work_type(),
    #     keyword=await Work.gen_keyword(),
    #     keyword_creater="天知遥",
    #     order=await Work.gen_order(new=True),
    #     per_page=50,
    #     page=1,
    #     show_type="box",
    #     AI_option=await Work.gen_AI_option(hide_AI_generate=True, hide_AI_use=True),
    # )
    # print(url)

    # 天知遥の発売中作品（発売日順）
    test_url = "https://www.dlsite.com/maniax/fsr/=/language/jp/ana_flg/on_sale/keyword_creater/%E5%A4%A9%E7%9F%A5%E9%81%A5/order/release_d/per_page/50/page/1/show_type/0/options_and_or/and/options_not%5B0%5D/AIG/options_not%5B1%5D/AIP/"

    # スクレイピング
    client = Work()
    await client.open_browser(debug=True)
    work_list = await client.search(url=test_url)
    # 書き出し
    with open("work_list.json", "w", encoding="utf-8") as f:
        json.dump(work_list, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    coloredlogs.install(level="DEBUG", logger=logger)
    asyncio.run(main())
