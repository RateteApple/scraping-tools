# coding: utf-8

from __future__ import annotations
from datetime import datetime, timedelta
import re
import requests
import json
import logging
import feedparser
import xmltodict

from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

from .common import set_year, get_matching_element
from my_utilities.debug_decorator import apply_output_debug


logger = logging.getLogger(__name__)


@apply_output_debug(logger, exclude=["_live_page", "_video_page", "_news_page"])
class NicoNicoChannel:
    """ニコニコチャンネルのコンテンツを取得するクラス"""

    # 正規表現パターン
    channel_id_pattern = re.compile(r"^ch\d+$")
    live_id_pattern = re.compile(r"^lv\d+$")
    video_id_pattern = re.compile(r"^so\d+$")
    news_id_pattern = re.compile(r"^ar\d+$")

    # ブラウザはヘッドレスモードがデフォルト
    is_headless = True
    # 要素が見つかるまでのデフォルトの待機時間
    default_wait_time = 5

    # コンストラクタ
    def __init__(self) -> None:
        """コンストラクタ"""
        pass

    # デストラクタ
    def __del__(self) -> None:
        """デストラクタ"""
        # ブラウザを終了
        self.driver.quit()
        logger.debug(f"close browser")

    # get attribute
    def __getattr__(self, name):
        """属性が見つからなかった場合の処理"""
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

            # ブラウザの待機時間を設定
            self.wait = WebDriverWait(self.driver, self.default_wait_time)
            return self.driver

    # トップページの生放送を取得するメソッド
    def top_live(self, channel_id, page: int = 1, limit: int = 20) -> list[dict]:
        """ニコニコチャンネルの生放送ページから一覧をスクレイピングする"""
        lives = []

        # チャンネルIDが間違った形式の場合はエラー
        if not re.match(pattern=self.channel_id_pattern, string=channel_id):
            raise self.InvalidChannelIdPatternError(channel_id)

        # ページを開く
        self.driver.get(f"https://ch.nicovideo.jp/{channel_id}/live")

        # 引数で指定されたページ数分ループ
        page_count = 1
        while True:
            # 1ページ目は放送中、放送予定、過去放送の全てを取得
            if page_count == 1:
                lives.extend(self._top_live_page(now=True, future=True, past=True))
            # 2ページ目以降は過去放送のみを取得
            else:
                lives.extend(self._top_live_page(now=False, future=False, past=True))

            # ページ数をカウントアップ
            page_count += 1

            # 取得したページ数が指定されたページ数に達したら終了
            if page_count > page:
                break
            # 取得したアイテム数が指定されたアイテム数に達したら終了
            if len(lives) >= limit:
                lives = lives[:limit]
                break

            # 次のページがあるかどうかを確認
            for _ in range(30):
                try:
                    next_buttons: list = self.driver.find_elements(By.XPATH, '//li[@class="next"]/a')  # 次へのボタン
                except StaleElementReferenceException:
                    next_disableds: list = self.driver.find_elements(By.XPATH, '//li[@class="next disabled"]')  # 次へのボタンが無効化された要素
                if next_buttons or next_disableds:  # どちらかが取得できればループを抜ける
                    break
            else:  # 30回ループしても取得できなければエラー
                raise Exception("ページ遷移処理に失敗")

            # 次のページに遷移
            if next_buttons:
                next_buttons[0].click()

        return lives

    def _top_live_page(self, now=True, future=True, past=True) -> list[dict]:
        lives = []
        item: WebElement

        icon_link: WebElement = get_matching_element(
            base_element=self.driver, tag="span", attribute="class", pattern=re.compile(r"^.*thumb_wrapper_ch.*$")
        )
        channel_title: str = icon_link.find_element(By.XPATH, "./a").get_attribute("title")
        channel_id: str = icon_link.find_element(By.XPATH, "./a").get_attribute("href").split("/")[-1]

        # 放送中
        if now:
            now_section: WebElement = self.wait.until(EC.presence_of_element_located((By.XPATH, '//section[@class="sub now"]')))
            items: list = now_section.find_elements(By.XPATH, './div[@id="live_now"]/div[@id="live_now_cnt"]/ul/li[@class="item"]')
            for item in items:
                now_live = {}
                now_live["channel_id"] = channel_id
                now_live["channel_title"] = channel_title
                now_live["status"] = "now"
                now_live["title"] = item.find_element(By.XPATH, './/p[@class="title"]').text
                now_live["link"] = item.find_element(By.XPATH, './/p[@class="title"]/a').get_attribute("href")
                now_live["id"] = now_live["link"].split("/")[-1]
                now_live["thumbnail_link"] = item.find_element(By.XPATH, ".//img").get_attribute("src")
                lives.append(now_live)

        # 放送予定
        if future:
            future_section: WebElement = self.wait.until(EC.presence_of_element_located((By.XPATH, '//section[@class="sub future"]')))
            items: list = future_section.find_elements(By.XPATH, './/li[@class="item"]')
            for item in items:
                future_live = {}
                future_live["channel_id"] = channel_id
                future_live["status"] = "future"
                future_live["title"] = item.find_element(By.XPATH, './/h2[@class="title"]').text
                future_live["link"] = item.find_element(By.XPATH, ".//h2[@class='title']/a").get_attribute("href")
                future_live["id"] = future_live["link"].split("/")[-1]
                future_live["thumbnail_link"] = item.find_element(By.XPATH, ".//img").get_attribute("src")
                scheduled_start_at: str = item.find_element(By.XPATH, './/p[@class="date"]/strong').text
                scheduled_start_at: str = re.sub(r"\s*\([^)]*\)", "", scheduled_start_at)  # 曜日部分を削除
                scheduled_start_at: datetime = datetime.strptime(scheduled_start_at, "%m月%d日 %H時%M分")  # datetime型に変換
                scheduled_start_at: datetime = set_year(scheduled_start_at)  # 年を設定
                future_live["scheduled_start_at"] = scheduled_start_at.isoformat()
                lives.append(future_live)

        # 過去放送
        if past:
            past_section: WebElement = self.wait.until(EC.presence_of_element_located((By.XPATH, '//section[@class="sub past"]')))
            items: list = past_section.find_elements(By.XPATH, './/li[@class="item"]')
            for item in items:
                past_live = {}
                past_live["channel_id"] = channel_id
                past_live["status"] = "past"
                past_live["title"] = item.find_element(By.XPATH, ".//h2").text
                past_live["link"] = item.find_element(By.XPATH, ".//h2/a").get_attribute("href")
                past_live["id"] = past_live["link"].split("/")[-1]
                past_live["thumbnail_link"] = item.find_element(By.XPATH, ".//img").get_attribute("src")
                actual_start_at: str = item.find_element(By.XPATH, './/p[@class="date"]').text  # ex:"放送開始：2023/09/04 (月) 22:50:00"
                actual_start_at: str = re.sub(r"\s*\([^)]*\)", "", actual_start_at)  # 曜日部分を削除
                actual_start_at: datetime = datetime.strptime(actual_start_at, "放送開始：%Y/%m/%d %H:%M:%S")  # datetime型に変換
                actual_start_at: datetime = set_year(actual_start_at)  # 年を設定
                past_live["actual_start_at"] = actual_start_at.isoformat()
                lives.append(past_live)

        return lives

    # トップページの動画を取得するメソッド
    def top_video(self, channel_id: str, page: int = 1, limit: int = 20) -> list[dict]:
        """ニコニコチャンネルの動画ページから動画をスクレイピングする"""
        videos = []
        item: WebElement

        # チャンネルIDが間違った形式の場合はエラー
        if not re.match(pattern=self.channel_id_pattern, string=channel_id):
            raise self.InvalidChannelIdPatternError(channel_id)

        # ページを開く
        self.driver.get(f"https://ch.nicovideo.jp/{channel_id}/video")

        page_count = 0
        while True:
            page_count += 1
            # アイテムを取得
            items = self.wait.until(EC.presence_of_all_elements_located((By.XPATH, '//li[@class="item"]')))
            # 動画情報を取得
            for item in items:
                video = {}
                video["channel_id"] = channel_id
                video["title"]: str = item.find_element(By.XPATH, ".//a").get_attribute("title")
                video["link"]: str = item.find_element(By.XPATH, ".//a").get_attribute("href")
                video["id"]: str = video["link"].split("/")[-1]
                video["thumbnail_link"]: str = item.find_element(By.XPATH, ".//img").get_attribute("src")
                published_at: str = item.find_element(By.XPATH, './/p[@class="time"]/time/var').get_attribute("title")  # ex:"2023/09/08 19:00"
                video["published_at"]: str = datetime.strptime(published_at, "%Y/%m/%d %H:%M").isoformat()
                video["view_count"]: int = int(item.find_element(By.XPATH, './/li[@class="view "]/var').text.replace(",", ""))
                video["comment_count"]: int = int(item.find_element(By.XPATH, './/li[@class="comment "]/var').text.replace(",", ""))
                video["my_list"]: int = int(item.find_element(By.XPATH, './/li[@class="mylist "]//var').text.replace(",", ""))
                length: str = item.find_element(By.XPATH, './/span[@class="badge br length"]').get_attribute("title")  # ex:"115:56"
                minute, second = length.split(":")
                video["length"]: str = timedelta(minutes=int(minute), seconds=int(second)).total_seconds()
                videos.append(video)
            # 取得したページ数が指定されたページ数に達したら終了
            if page_count >= page:
                break
            # 取得したアイテム数が指定されたアイテム数に達したら終了
            if len(videos) >= limit:
                videos = videos[:limit]
                break
            # 次のページがあるかどうかを確認
            for _ in range(30):
                try:
                    next_buttons: list = self.driver.find_elements(By.XPATH, '//li[@class="next"]/a')  # 次へのボタン
                except StaleElementReferenceException:
                    next_disableds: list = self.driver.find_elements(By.XPATH, '//li[@class="next disabled"]')  # 次へのボタンが無効化された要素
                if next_buttons or next_disableds:  # どちらかが取得できればループを抜ける
                    break
            else:  # 30回ループしても取得できなければエラー
                raise Exception("ページ遷移処理に失敗")
            # 次のページに遷移
            if next_buttons:
                next_buttons[0].click()

        return videos

    # トップページのニュースを取得するメソッド
    def top_news(self, channel_id: str, limit: int = 20) -> str:
        """ニコニコチャンネルのニュースをfeedを使って取得する"""
        newses = []

        # チャンネルIDが間違った形式の場合はエラー
        if not re.match(pattern=self.channel_id_pattern, string=channel_id):
            raise self.InvalidChannelIdPatternError(channel_id)

        # RSSフィードを取得
        feed = feedparser.parse(f"https://ch.nicovideo.jp/{channel_id}/blomaga/nico/feed")

        # ステータスコードが400番以上の場合に例外
        if feed["status"] >= 400:
            raise Exception("ニュースの取得に失敗しました")
        # XMLデータが不正な場合に例外
        if feed["bozo"] == 1:
            raise Exception("XMLデータが不正です")
        # ニュースのアイテムが存在しない場合は空のリストを返す
        if len(feed["entries"]) == 0:
            return []

        # ニュースのアイテムを取得
        for entry in feed["entries"]:
            news = {}
            news["channel_id"] = channel_id
            news["id"]: str = entry["id"].split("/")[-1]
            news["title"]: str = entry["title"]
            news["link"]: str = entry["link"]
            news["thumbnail_link"]: str = entry["nicoch_article_thumbnail"]
            published_at: datetime = datetime.strptime(entry["published"], "%a, %d %b %Y %H:%M:%S %z")
            news["published_at"]: str = published_at.isoformat()
            newses.append(news)

        # 指定された数だけニュースを取得
        newses = newses[:limit]

        return newses

    # 生放送の詳細情報を取得するメソッド
    def live(self, live_id: str):
        """生放送の詳細情報を取得する"""
        # live_idを指定した場合
        live = self._live_page(live_id)
        return live

    # 複数の生放送の詳細情報を取得するメソッド
    def lives(self, live_ids: list[str]):
        """複数の生放送の詳細情報を取得する"""
        lives = []
        for live_id in live_ids:
            lives.append(self._live_page(live_id))
        return lives

    def _live_page(self, live_id: str) -> dict:
        """生放送の詳細情報をスクレイピングで取得する"""
        live = {}

        # 生放送IDが間違った形式の場合はエラー
        if not re.match(pattern=self.live_id_pattern, string=live_id):
            raise self.InvalidLiveIdPatternError(live_id)

        # ページを開く
        self.driver.get(f"https://live.nicovideo.jp/watch/{live_id}")

        # JSON-LDタグを取得
        json_ld: WebElement = self.wait.until(EC.presence_of_element_located((By.XPATH, '//script[@type="application/ld+json"]')))
        json_ld: str = json_ld.get_attribute("innerHTML")
        json_ld: str = json.loads(json_ld)

        live["link"]: str = json_ld["embedUrl"]
        live["id"]: str = live["link"].split("/")[-1]
        author_link = json_ld["author"]["url"].split("/")
        live["user_id"]: str = author_link[-1] if author_link[-2] == "user" else None
        live["channel_id"]: str = author_link[-2] if author_link[-1] == "join" else None
        live["title"]: str = json_ld["publication"]["name"]
        live["thumbnail_link"]: str = json_ld["thumbnailUrl"][0]
        live["tags"]: list = json_ld["keywords"]
        live["description"]: str = get_matching_element(
            base_element=self.driver, tag="div", attribute="class", pattern=re.compile(r"^___description___.*$")
        ).text

        # 生放送の種類を判別（放送予定、放送中、過去放送）
        for _ in range(30):
            # タイムシフトの公開期間を取得
            timeshift_element = get_matching_element(
                base_element=self.driver, tag="time", attribute="class", pattern=re.compile(r"^___program-viewing-period-date-time___.*$")
            )
            # 動画上に表示されるメッセージを取得
            message_element = get_matching_element(
                base_element=self.driver, tag="p", attribute="class", pattern=re.compile(r"^___primary-message___.*$")
            )
            # LIVE中のボタンを取得
            live_button: list = self.driver.find_elements(By.XPATH, '//button[@data-live-status="live"]')
            # 分類
            if timeshift_element:
                live["status"] = "past"
                live["is_timeshift_enabled"] = True
                timeshift_limit_at: str = timeshift_element.get_attribute("datetime")
                live["timeshift_limit_at"] = datetime.strptime(timeshift_limit_at, "%Y-%m-%d %H:%M:%S").isoformat()
                break
            elif message_element.text == "放送開始までしばらくお待ちください":
                live["status"] = "future"
                live["scheduled_start_at"] = json_ld["publication"]["startDate"]
                break
            elif message_element.text == "タイムシフトの公開期間が終了しました":
                live["status"] = "past"
                live["is_timeshift_enabled"] = False
                break
            elif live_button:
                live["status"] = "now"
                break
            # 待機して次のループ
            self.driver.implicitly_wait(0.2)
            continue

        # 放送の開始時間、終了時間、長さ(過去放送のみ)
        if live["status"] == "past":
            live["actual_start_at"] = json_ld["publication"]["startDate"]  # ISO8601形式
            live["actual_end_at"] = json_ld["publication"]["endDate"]
            start_date = datetime.fromisoformat(json_ld["publication"]["startDate"])
            end_date = datetime.fromisoformat(json_ld["publication"]["endDate"])
            length: timedelta = end_date - start_date
            live["length"]: int = int(length.total_seconds())

        return live

    # 動画の詳細情報を取得するメソッド
    def video(self, video_id: str):
        """動画の詳細情報を取得する"""
        video = self._video_page(video_id)
        return video

    # 複数の動画の詳細情報を取得するメソッド
    def videos(self, video_ids: list[str]) -> list[dict]:
        """複数の動画の詳細情報を取得する"""
        videos = []
        for video_id in video_ids:
            videos.append(self._video_page(video_id))
        return videos

    def _video_page(self, video_id: str) -> dict:
        """動画の詳細情報をAPIを使って取得する"""
        # 動画IDが間違った形式の場合はエラー
        if not re.match(pattern=self.video_id_pattern, string=video_id):
            raise self.InvalidVideoIdPatternError(video_id)

        # 動画情報を取得
        res = requests.get(f"https://ext.nicovideo.jp/api/getthumbinfo/{video_id}")
        if res.status_code != 200:
            raise Exception(f"動画情報の取得に失敗しました。[status_code:{res.status_code}]")

        # dict型に変換
        res.text.encode("utf-8")
        res_dict = xmltodict.parse(res.text)

        # データを取得
        video = {}
        video["content_type"] = "video"
        video["id"]: str = video_id
        video["channel_id"]: str = "ch" + res_dict["nicovideo_thumb_response"]["thumb"]["ch_id"]
        video["title"]: str = res_dict["nicovideo_thumb_response"]["thumb"]["title"]
        video["description"]: str = res_dict["nicovideo_thumb_response"]["thumb"]["description"]
        video["link"]: str = res_dict["nicovideo_thumb_response"]["thumb"]["watch_url"]
        video["thumbnail_link"]: str = res_dict["nicovideo_thumb_response"]["thumb"]["thumbnail_url"]
        video["published_at"]: str = res_dict["nicovideo_thumb_response"]["thumb"]["first_retrieve"]
        length_text: str = res_dict["nicovideo_thumb_response"]["thumb"]["length"]
        minute, second = length_text.split(":")
        video["length"]: int = timedelta(minutes=int(minute), seconds=int(second)).total_seconds()
        video["view_count"]: int = int(res_dict["nicovideo_thumb_response"]["thumb"]["view_counter"])
        video["comment_count"]: int = int(res_dict["nicovideo_thumb_response"]["thumb"]["comment_num"])
        video["is_deleted"]: bool = True if res_dict["nicovideo_thumb_response"]["@status"] == "fail" else False

        return video

    # ニュースの詳細情報を取得するメソッド
    def news(self, channel_id: str, news_id: str) -> dict:
        """ニュースの詳細情報を取得する"""
        news = self._news_page(channel_id, news_id)
        return news

    # 複数のニュースの詳細情報を取得するメソッド
    def newses(self, channel_id: str, news_ids: list[str]) -> list[dict]:
        """複数のニュースの詳細情報を取得する"""
        newses = []
        for news_id in news_ids:
            newses.append(self._news_page(channel_id, news_id))
        return newses

    def _news_page(self, channel_id: str, news_id: str) -> dict:
        """ニュースの詳細情報を取得する"""
        # チャンネルIDが間違った形式の場合はエラー
        if not re.match(pattern=self.channel_id_pattern, string=channel_id):
            raise self.InvalidChannelIdPatternError(channel_id)

        # ニュースIDが間違った形式の場合はエラー
        if not re.match(pattern=self.news_id_pattern, string=news_id):
            raise self.InvalidNewsIdPatternError(news_id)

        # ニュースのページを開く
        self.driver.get(f"https://ch.nicovideo.jp/{channel_id}/blomaga/{news_id}")

        news = {}
        news["channel_id"]: str = channel_id
        news["id"]: str = news_id
        news["title"]: str = self.wait.until(EC.presence_of_element_located((By.XPATH, '//h1[@id="article_blog_title"]'))).text
        news["link"]: str = self.driver.current_url
        news["thumbnail_link"]: str = self.driver.find_element(By.XPATH, '//div[@class="main_blog_txt"]//img').get_attribute("src")
        published_at_text: str = self.driver.find_element(By.XPATH, '//div[@class="article_blog_data_first"]/span').text  # ex:2022-09-02 19:00
        news["published_at"]: str = datetime.strptime(published_at_text, "%Y-%m-%d %H:%M").isoformat()
        # TODO: タグの取得
        news["text"]: str = self.wait.until(EC.presence_of_element_located((By.XPATH, '//div[@class="main_blog_txt"]'))).text

        return news

    # チャンネルIDの形式が不正な場合の例外
    class InvalidChannelIdPatternError(Exception):
        def __init__(self, video_id):
            super().__init__(f"Invalid video ID: {video_id}")

    # 生放送IDの形式が不正な場合の例外
    class InvalidLiveIdPatternError(Exception):
        def __init__(self, live_id):
            super().__init__(f"Invalid live ID: {live_id}")

    # 動画IDの形式が不正な場合の例外
    class InvalidVideoIdPatternError(Exception):
        def __init__(self, video_id):
            super().__init__(f"Invalid video ID: {video_id}")

    # ニュースIDの形式が不正な場合の例外
    class InvalidNewsIdPatternError(Exception):
        def __init__(self, news_id):
            super().__init__(f"Invalid news ID: {news_id}")
