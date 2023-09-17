# coding: utf-8

from __future__ import annotations
import logging
from datetime import datetime, timedelta
import time
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException

from .common import set_year, get_matching_element, get_matching_all_elements, ScrapingClass, Platform, Content, Live, Video, News
from my_utilities.debug import execute_time


logger = logging.getLogger(__name__)

root_xpath: str = '//div[@id="root"]'
header_xpath: str = '//div[@id="root"]/div/div[1]'
main_xpath: str = '//div[@id="root"]/div/div[2]/div[1]'
footer_xpath: str = '//div[@id="root"]/div/div[2]/div[2]'
not_found_xpath: str = '//h5[text()="ページを表示することができませんでした"]'
not_found_xpath2: str = '//h5[text()="お探しのページは見つかりませんでした"]'


@execute_time()
class Channel(ScrapingClass):
    """ニコニコチャンネルプラスのコンテンツを取得するクラス"""

    # コンストラクタ
    def __init__(self):
        """コンストラクタ"""
        pass

    # デストラクタ
    def __del__(self):
        """デストラクタ"""
        # ブラウザを終了
        self.driver.quit()
        logger.debug(f"close browser")

    # get attribute
    def __getattr__(self, name):
        """属性が見つからなかった場合の処理"""
        # メソッド名の提案
        if name == "video":
            error_message = "video()は存在しません。content()を使ってください。"
            raise AttributeError(error_message)
        elif name == "live":
            error_message = "live()は存在しません。content()を使ってください。"
            raise AttributeError(error_message)

        # driverが起動されていない場合、起動する
        if name == "driver":
            # ブラウザのオプションを設定
            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            if self.is_headless:
                options.add_argument("--headless")

            # ブラウザを起動
            if self.is_headless:
                logger.debug(f"open browser : headless mode")
            else:
                logger.debug(f"open browser : GUI mode")
            self.driver = webdriver.Chrome(options=options)

            # 待機時間を設定
            self.wait = WebDriverWait(self.driver, self.default_wait_time)
            self.retry_count: int = int(self.default_wait_time / self.retry_interval)

            return self.driver

    # トップページの生放送を取得するメソッド
    def top_live(self, channel_id: str) -> list[dict]:
        """ニコニコチャンネルプラスの生放送ページから配信中の放送と放送予定を取得するメソッド"""
        lives = []

        # 生放送ページを開く
        self.driver.get(f"https://nicochannel.jp/{channel_id}/lives")

        # セクションを取得出来るまでリトライ
        for _ in range(self.retry_count):
            sections: list = self.driver.find_elements(By.XPATH, f"{self.main_xpath}/div/div")
            if len(sections) >= 2:
                break
            time.sleep(self.retry_interval)  # FIXME: 可能であれば非同期処理にする
        # セクションが取得出来なかった場合はエラーを投げる
        else:
            if self.driver.find_element(By.XPATH, self.not_found_xpath):
                raise ValueError(f"maybe channel_id is wrong (ID:{channel_id})")
            else:
                raise ValueError(f"unknown error (URL:{self.driver.current_url})")

        # 放送中か判定
        if len(sections) == 3:
            logger.debug(f"streaming now")
            now_section: WebElement = sections[0]
            future_section: WebElement = sections[1]
        else:
            now_section: WebElement = None
            future_section: WebElement = sections[0]

        # 放送中の生放送
        if now_section:
            # 放送中の生放送情報を取得
            live = {}
            live["channel_id"]: str = channel_id
            live["status"]: str = "now"
            # TODO: 放送中の生放送の情報を取得する
            lives.append(live)

        # 放送予定
        for _ in range(30):
            items = get_matching_all_elements(
                base_element=future_section, tag="a", attribute="class", pattern=re.compile(r"^MuiButtonBase-root MuiCardActionArea-root.*$")
            )  # //*[@id="app-layout"]/div[2]/div[1]/div[1]/div/div/div/div/a
            if items:
                break
            # 待機して次のループ
            time.sleep(self.retry_interval)  # FIXME: 可能であれば非同期処理にする
            continue

        for item in items:
            item: WebElement
            live = {}
            # 各種情報
            live["channel_id"]: str = channel_id
            live["status"]: str = "future"
            live["title"]: str = item.find_element(By.XPATH, "div[2]/div[1]/h6").text
            live["link"]: str = item.get_attribute("href")
            live["id"]: str = live["link"].split("/")[-1]
            # サムネイル
            thumbnail: str = item.find_element(By.XPATH, "div").get_attribute("style")
            live["thumbnail_link"]: str = re.search(r"https.*(\d+)", thumbnail).group()
            # 開始予定時刻
            scheduled_start_at: str = get_matching_element(
                base_element=item, tag="span", attribute="class", pattern=re.compile(r"^.*MuiTypography-caption.*$")
            ).text  # ex:'09/16 21:00', '今日 21:00' etc...
            if "今日" in scheduled_start_at:  # 日付部分の補完
                scheduled_start_at: str = scheduled_start_at.replace("今日", datetime.now().strftime("%m/%d"))
            elif "明日" in scheduled_start_at:
                scheduled_start_at: str = scheduled_start_at.replace("明日", (datetime.now() + timedelta(days=1)).strftime("%m/%d"))
            scheduled_start_at: datetime = datetime.strptime(scheduled_start_at, "%m/%d %H:%M")  # datetime型に変換
            scheduled_start_at: datetime = set_year(scheduled_start_at)  # 年部分を補完
            live["scheduled_start_at"]: str = scheduled_start_at.isoformat()
            # リストに追加する
            lives.append(live)

        return lives

    # トップページの動画を取得するメソッド
    def top_video(self, channel_id: str, type: str = "upload") -> list[dict]:
        """ニコニコチャンネルプラスの動画ページをスクレイピングする"""
        videos = []

        # 動画ページを開く
        self.driver.get(f"https://nicochannel.jp/{channel_id}/videos")

        # 指定されたタイプのボタンをクリックして遷移
        try:
            if type == "upload":
                self.wait.until(EC.element_to_be_clickable((By.XPATH, '//span[text()="アップロード動画"]/..'))).click()
            elif type == "archive":
                self.wait.until(EC.element_to_be_clickable((By.XPATH, '//span[text()="アーカイブ動画"]/..'))).click()
            elif type == "all":
                pass
            else:
                raise ValueError("type must be 'upload' or 'archive' or 'all'")
        # 要素が見つからなかった場合エラーを投げる
        except TimeoutException:
            if self.driver.find_element(By.XPATH, self.not_found_xpath):
                raise ValueError(f"maybe channel_id is wrong (ID:{channel_id})")
            else:
                raise ValueError(f"unknown error (URL:{self.driver.current_url})")

        # アイテムを取得
        items = []
        for _ in range(30):
            main: WebElement = self.driver.find_element(By.XPATH, '//div[@id="root"]/div/div[2]/div[1]')
            items: list = get_matching_all_elements(base_element=main, tag="div", attribute="class", pattern=re.compile(r"^.*MuiGrid-item.*$"))
            # アイテムが取得できたらループを抜ける
            if items:
                break
            time.sleep(self.retry_interval)  # FIXME: 可能であれば非同期処理にする

        # 各アイテムから動画情報を取得
        for item in items:
            video = {}
            item_upper: WebElement = item.find_element(By.XPATH, "./div/div/div[1]")
            item_under: WebElement = item.find_element(By.XPATH, "./div/div/div[2]")
            # 各種情報を取得
            video["channel_id"]: str = channel_id
            video["title"]: str = item_under.find_element(By.XPATH, ".//h6").text
            video["link"]: str = item_under.find_element(By.XPATH, ".//a").get_attribute("href")
            video["id"]: str = video["link"].split("/")[-1]
            video["thumbnail_link"]: str = item_upper.find_element(By.XPATH, ".//img").get_attribute("src")
            uploaded_at: str = item_under.find_element(By.XPATH, ".//span").text  # ex:"2023/07/06", "〇日前"
            if "日前" in uploaded_at:  # 日付部分の補完
                before_days: int = int(uploaded_at[0])
                uploaded_at: str = (datetime.now() - timedelta(days=before_days)).strftime("%Y/%m/%d")
            video["uploaded_at"]: str = datetime.strptime(uploaded_at, "%Y/%m/%d").isoformat()
            length: str = item_upper.find_element(By.XPATH, "./div[2]").text  # 00:00:00
            length: timedelta = self.__parse_video_duration(length)
            video["length"]: int = int(timedelta.total_seconds(length))  # 秒数に変換
            video["view_count"]: int = int(item_under.find_element(By.XPATH, "./div/div/div[1]/div").text)
            video["comment_count"]: int = int(item_under.find_element(By.XPATH, "./div/div/div[2]/div").text)
            # リストに追加する
            videos.append(video)

        return videos

    # 動画時間文字列を時間、分、秒に分割する関数
    def __parse_video_duration(duration_str: str) -> timedelta:
        """動画時間文字列を時間、分、秒に分割する

        '00:00:00'もしくは'00:00'のような形式で引数を渡す
        """
        # 時間、分、秒の要素を取得
        parts: list = duration_str.split(":")
        if len(parts) == 3:
            seconds: int = int(parts[-1])
            minutes: int = int(parts[-2])
            hours: int = int(parts[-3])
        elif len(parts) == 2:
            seconds: int = int(parts[-1])
            minutes: int = int(parts[-2])
            hours: int = 0
        else:
            raise ValueError(f"invalid duration_str (duration_str:{duration_str})")

        # timedelta オブジェクトを作成
        video_duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)

        return video_duration

    # トップページのニュースを取得するメソッド
    def top_news(self, channel_id: str, full_info: bool = False) -> list[dict]:
        """ニコニコチャンネルプラスのニュースページをスクレイピングする

        full_infoがTrueの場合はニュースの詳細情報も取得する
        """
        # トップページのニュースを取得
        newses = self._top_news_page(channel_id)

        # full_infoがTrueの場合はニュースの詳細情報も取得する
        if full_info:
            for number, top_news in enumerate(newses):
                # 新しいタブを開く
                current_tab = self.driver.current_window_handle
                self.driver.switch_to.new_window("tab")
                # 新しいタブに遷移するまで待機
                while current_tab == self.driver.current_window_handle:
                    time.sleep(self.retry_interval)  # FIXME: 可能であれば非同期処理にする
                # ページを開いてIDを取得
                self.driver.get(f"https://nicochannel.jp/{channel_id}/articles/news")
                self.wait.until(EC.element_to_be_clickable((By.XPATH, f'//h6[text()="{top_news["title"]}"]'))).click()
                news_id = self.driver.current_url.split("/")[-1]
                detail_news: dict = self._news_page(channel_id, news_id)
                # 辞書を1つに統合
                newses[number] = top_news | detail_news
                # タブを閉じて元のタブに戻る
                self.driver.close()
                self.driver.switch_to.window(current_tab)
                # 1秒待機
                time.sleep(1)  # FIXME: 可能であれば非同期処理にする

        return newses

    def _top_news_page(self, channel_id: str) -> list[dict]:
        newses = []
        item: WebElement

        # ニュースページを開く
        self.driver.get(f"https://nicochannel.jp/{channel_id}/articles/news")

        # メインの要素が取得
        try:
            main = self.wait.until(EC.presence_of_element_located((By.XPATH, self.main_xpath)))
        # 要素が見つからなかった場合エラーを投げる
        except TimeoutException:
            if self.driver.find_element(By.XPATH, self.not_found_xpath):
                raise ValueError(f"maybe channel_id is wrong (ID:{channel_id})")
            else:
                raise ValueError(f"unknown error (URL:{self.driver.current_url})")

        # アイテムを取得
        for _ in range(self.retry_count):
            items = get_matching_all_elements(base_element=main, tag="div", attribute="class", pattern=re.compile(r"^.*MuiPaper-rounded.*$"))
            if items:
                break
            time.sleep(self.retry_interval)  # FIXME: 可能であれば非同期処理にする
        # アイテムがない場合は空のリストを返す
        else:
            logger.debug(f"can't get items. maybe no news or error occurred.")  # FIXME
            return []

        # FIXME: 各ニュースから情報を取得
        for item in items:
            news = {}
            for _ in range(self.retry_count):
                # 情報を取得する
                try:
                    news["channel_id"]: str = channel_id
                    news["title"]: str = item.find_element(By.XPATH, ".//h6").text
                    news["thumbnail_link"]: str = item.find_element(By.XPATH, ".//img").get_attribute("src")
                    published_at: str = item.find_element(By.XPATH, "./div[2]/div[3]/div").text  # ex:"2023/07/06","2日前"
                    try:
                        news["published_at"]: str = datetime.strptime(published_at, "%Y/%m/%d").isoformat()
                    except ValueError:
                        before_days: int = int(published_at[0])
                        news["published_at"]: str = (datetime.now() - timedelta(days=before_days)).isoformat()
                # 要素が見つからなかった時
                except NoSuchElementException:
                    time.sleep(self.retry_interval)
                # 成功時
                else:
                    newses.append(news)
                    break
            else:
                raise ValueError(f"can't get news info (URL:{self.driver.current_url})")

        return newses

    # 生放送か動画の詳細情報を取得するメソッド
    def content(self, channel_id: str, content_id: str) -> dict:
        """生放送と動画の詳細情報を取得する"""

        content = self._content_page(channel_id, content_id)

        return content

    # 複数の生放送か動画の詳細情報を取得するメソッド
    def contents(self, channel_id: str, content_ids: list[str]) -> list[dict]:
        """生放送と動画の詳細情報を取得する"""

        contents = []
        for content_id in content_ids:
            content = self._content_page(channel_id, content_id)
            contents.append(content)

        return contents

    def _content_page(self, channel_id: str, content_id: str) -> dict:
        """生放送、動画ページをスクレイピングする"""
        content = {}

        # コンテンツのページを開く
        self.driver.get(f"https://nicochannel.jp/{channel_id}/live/{content_id}")

        # メインの要素を取得
        try:
            self.wait.until(EC.presence_of_element_located((By.XPATH, self.main_xpath)))
        except TimeoutException:
            if self.driver.find_element(By.XPATH, self.not_found_xpath):
                raise ValueError(f"maybe channel_id is wrong (ID:{channel_id})")

        # コンテンツ情報を取得
        try:
            # 各種情報
            content["link"]: str = self.driver.current_url
            content["id"]: str = content["link"].split("/")[-1]
            content["channel_id"]: str = content["link"].split("/")[-3]
            content["title"]: str = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '/html/head/meta[@property="og:title"]'))
            ).get_attribute("content")
            content["thumbnail_link"]: str = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '/html/head/meta[@property="og:image"]'))
            ).get_attribute("content")
            content["description"]: str = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '/html/head/meta[@name="description"]'))
            ).get_attribute("content")
            # 放送予定、放送中の判定
            self.wait.until(EC.presence_of_element_located((By.XPATH, '//div[@id="video-page-wrapper"]')))
            labels: list = self.driver.find_elements(By.XPATH, '//span[@class="MuiChip-label MuiChip-labelSmall"]')
            for label in labels:
                # 放送予定
                if label.text == "COMING SOON":
                    content["type"]: str = "live"
                    content["status"]: str = "future"
                    break
                # 放送中
                elif label.text == "ON AIR":  # FIXME:てきとう
                    content["type"]: str = "live"
                    content["status"]: str = "now"
                    break

        # 要素が見つからなかった場合エラーを投げる
        except TimeoutException:
            if self.driver.find_element(By.XPATH, self.not_found_xpath2):
                raise ValueError(f"maybe content_id is wrong (channel_id:{channel_id}, content_id:{content_id})")
            else:
                raise ValueError(f"unknown error (ID:{channel_id}, content_id:{content_id})")

        return content

    # ニュースの詳細情報を取得するメソッド
    def news(self, channel_id: str, news_id: str = None) -> dict:
        """ニュースの詳細情報をスクレイピングで取得する"""
        news = {}

        # ニュースページから情報を取得
        news = self._news_page(channel_id, news_id)

        # トップページから情報を取得
        top_newses = self.top_news(channel_id)

        # トップページのニュースの中からタイトルが一致するものを見つけ合成
        for top_news in top_newses:
            if top_news["title"] == news["title"]:
                news = top_news | news
                break

        return news

    def _news_page(self, channel_id: str, news_id: str = None) -> dict:
        """news()の内部で使うニュースページの情報を取得するメソッド"""
        news = {}

        # ニュースページを開く
        self.driver.get(f"https://nicochannel.jp/{channel_id}/articles/news/{news_id}")

        # メインの要素を取得出来ない場合はエラーを投げる
        try:
            self.wait.until(EC.presence_of_element_located((By.XPATH, self.main_xpath)))
        except TimeoutException:
            if self.driver.find_element(By.XPATH, self.not_found_xpath):
                raise ValueError(f"maybe channel_id is wrong (URL:{self.driver.current_url})")
            else:
                raise ValueError(f"unknown error (URL:{self.driver.current_url})")

        # 各種情報を取得
        try:
            news["link"]: str = self.driver.current_url
            news["title"]: str = self.driver.title
            news["id"]: str = news["link"].split("/")[-1]
            news["channel_id"]: str = news["link"].split("/")[-4]
            published_at: str = self.wait.until(
                EC.presence_of_element_located((By.XPATH, f"{self.main_xpath}/div[2]/div[4]/span"))
            ).text  # ex:"2022/02/10" or "2日前"
            try:
                news["published_at"]: str = datetime.strptime(published_at, "%Y/%m/%d").isoformat()
            except ValueError:
                before_days: int = int(published_at[0])
                news["published_at"]: str = (datetime.now() - timedelta(days=before_days)).isoformat()
            news["text"]: str = self.wait.until(EC.presence_of_element_located((By.XPATH, f"{self.main_xpath}/div[2]/div[5]"))).text
        except TimeoutException:
            if self.driver.find_element(By.XPATH, self.not_found_xpath2):
                raise ValueError(f"maybe news_id is wrong (URL:{self.driver.current_url})")

        return news


class Video(Video):
    pass


class Live(Live):
    pass


class News(News):
    pass
