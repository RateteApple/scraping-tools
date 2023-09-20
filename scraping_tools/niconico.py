from __future__ import annotations
from datetime import datetime, timedelta
import re
import requests
import json
import logging
import feedparser
import xml.etree.ElementTree as ET

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from bs4 import BeautifulSoup

from .base_class import ScrapingMixin, Platform, Live, Video, News
from .common_func import get_matching_element
from my_utilities.debug import execute_time


logger = logging.getLogger(__name__)

CHANNEL_ID_PATTERN = "^ch\d+$"
LIVE_ID_PATTERN = "^lv\d+$"
VIDEO_ID_PATTERN = "^so\d+$"
NEWS_ID_PATTERN = "^ar\d+$"


@execute_time()
class NicoNicoChannel(Platform, ScrapingMixin):
    """ニコニコチャンネルのコンテンツを取得するクラス"""

    def __init__(self, id: str) -> None:
        """チャンネルIDを指定する

        名前でもおそらく動くが動作は保証できない"""
        check_channel_id(id)
        super().__init__(id)

    # トップページの全てのコンテンツを取得する
    def get_all(self, limit_live: int = 10, limit_video: int = 20, limit_news: int = 5) -> tuple[list[NicoNicoLive], list[NicoNicoVideo], list[NicoNicoChannel.News]]:
        """ニコニコチャンネルに含まれる全てのコンテンツを取得する"""
        lives = self.get_live(limit_live)
        videos = self.get_video(limit_video)
        newses = self.get_news(limit_news)

        return lives, videos, newses

    # トップページの生放送を取得する
    def get_live(self, limit: int = 10) -> list[NicoNicoLive]:
        """ニコニコチャンネルの生放送ページから一覧をスクレイピングする

        1ページには大体10個の生放送が含まれている（放送予定、放送中の要素がある場合は増える）
        """
        lives = self.__live_page_loop(limit)
        return lives

    def __live_page_loop(self, limit: int) -> list[NicoNicoLive]:
        """ニコニコチャンネルの生放送ページから一覧をスクレイピングする"""
        lives = []

        # 取得したアイテム数がlimitに達するまでループ
        page = 0
        while len(lives) < limit:
            # ページカウントを進める
            page += 1

            # ページを開く
            self.driver.get(f"https://ch.nicovideo.jp/{self.id}/live?page={page}")

            # 1ページ目は放送中、放送予定、過去放送の全てを取得
            if page == 1:
                lives.extend(self.__live_page(now=True, future=True, past=True))
            # 2ページ目以降は過去放送のみを取得
            else:
                lives.extend(self.__live_page(now=False, future=False, past=True))

            # FIXME: 次のページがあるかどうかを確認
            for _ in range(30):
                next_buttons: list = self.driver.find_elements(By.XPATH, '//li[@class="next"]/a')
                next_disableds: list = self.driver.find_elements(By.XPATH, '//li[@class="next disabled"]')
                if next_buttons or next_disableds:
                    break
            else:
                raise  # FIXME

        return lives

    def __live_page(self, now=True, future=True, past=True) -> list[NicoNicoLive]:
        lives = []

        # 投稿者の名前とIDを取得
        icon_link: WebElement = get_matching_element(base=self.driver, tag="span", attribute="class", pattern=r"^.*thumb_wrapper_ch.*$")
        poster_name: str = icon_link.find_element(By.XPATH, "./a").get_attribute("title")
        poster_id: str = icon_link.find_element(By.XPATH, "./a").get_attribute("href").split("/")[-1]

        # 放送中
        if now:
            now_section: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//section[@class="sub now"]')))
            lives.extend(self.__now_section(now_section, poster_id, poster_name))
        # 放送予定
        if future:
            future_section: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//section[@class="sub future"]')))
            lives.extend(self.__future_section(future_section, poster_id, poster_name))
        # 過去放送
        if past:
            past_section: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//section[@class="sub past"]')))
            lives.extend(self.__past_section(past_section, poster_id, poster_name))

        return lives

    def __now_section(self, section: WebElement, poster_id: str, poster_name: str) -> list[NicoNicoLive]:
        lives = []
        item: WebElement
        # アイテム要素を取得
        items: list = section.find_elements(By.XPATH, './div[@id="live_now"]/div[@id="live_now_cnt"]/ul/li[@class="item"]')
        # アイテムから情報を取得
        for item in items:
            # 状態
            status = "now"
            # タイトル
            title = item.find_element(By.XPATH, './/p[@class="title"]').text
            # URL
            url = item.find_element(By.XPATH, './/p[@class="title"]/a').get_attribute("href")
            # ID
            id = url.split("/")[-1]
            # サムネイル
            thumbnail = item.find_element(By.XPATH, ".//img").get_attribute("src")

            # 生放送情報を追加
            live = NicoNicoLive(id)
            live.poster_id = poster_id
            live.poster_name = poster_name
            live.status = status
            live.title = title
            live.url = url
            live.thumbnail = thumbnail
            lives.append(live)

        # 結果を返す
        return lives

    def __future_section(self, section: WebElement, poster_id: str, poster_name: str) -> list[NicoNicoLive]:
        lives = []
        item: WebElement

        # アイテム要素を取得
        items: list = section.find_elements(By.XPATH, './/li[@class="item"]')
        for item in items:
            # 状態
            status = "future"
            # タイトル
            title: str = item.find_element(By.XPATH, './/h2[@class="title"]').text
            # URL
            url: str = item.find_element(By.XPATH, ".//h2[@class='title']/a").get_attribute("href")
            # ID
            id: str = url.split("/")[-1]
            # サムネイル
            thumbnail: str = item.find_element(By.XPATH, ".//img").get_attribute("src")
            # 開始日時
            start_at: str = item.find_element(By.XPATH, './/p[@class="date"]/strong').text  # ex:"09月23日 (土) 22時00分"
            start_at: str = re.sub(r"\s*\([^)]*\)", "", start_at)  # 曜日部分を削除 ex:"09月23日 (土) 22時00分" -> "09月23日 22時00分"
            start_at: datetime = datetime.strptime(start_at, "%m月%d日 %H時%M分")  # datetime型に変換
            now = datetime.now()
            if datetime.now().month > start_at.month:  # 月をまたいでいる場合は来年の月にする
                start_at = start_at.replace(year=now.year + 1)
            else:
                start_at = start_at.replace(year=now.year)

            # 生放送情報を追加
            live = NicoNicoLive(id)
            live.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                status=status,
                title=title,
                url=url,
                thumbnail=thumbnail,
                start_at=start_at.isoformat(),
            )

        # 結果を返す
        return lives

    def __past_section(self, section: WebElement, poster_id: str, poster_name: str) -> list[NicoNicoLive]:
        lives = []
        item: WebElement
        # アイテム要素を取得
        items: list = section.find_elements(By.XPATH, './/li[@class="item"]')
        # アイテムから情報を取得
        for item in items:
            # 状態
            status = "past"
            # タイトル
            title = item.find_element(By.XPATH, ".//h2").text
            # URL
            url = item.find_element(By.XPATH, ".//h2/a").get_attribute("href")
            # ID
            id = url.split("/")[-1]
            # サムネイル
            thumbnail = item.find_element(By.XPATH, ".//img").get_attribute("src")
            # 開始日時
            actual_start_at: str = item.find_element(By.XPATH, './/p[@class="date"]').text  # ex:"放送開始：2023/09/04 (月) 22:50:00"
            actual_start_at: str = re.sub(r"\s*\([^)]*\)", "", actual_start_at)  # 曜日部分を削除
            actual_start_at: datetime = datetime.strptime(actual_start_at, "放送開始：%Y/%m/%d %H:%M:%S")  # datetime型に変換

            # 生放送情報を追加
            live = NicoNicoLive(id)
            live.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                status=status,
                title=title,
                url=url,
                thumbnail=thumbnail,
                start_at=actual_start_at.isoformat(),
            )
            lives.append(live)

        # 結果を返す
        return lives

    # トップページの動画を取得する
    def get_video(self, limit: int = 20) -> list[NicoNicoVideo]:
        """ニコニコチャンネルの動画ページから一覧をスクレイピングする"""
        videos = self.__video_page_loop(limit)
        return videos

    def __video_page_loop(self, limit: int) -> list[NicoNicoVideo]:
        """ニコニコチャンネルの動画ページから一覧をスクレイピングする"""
        videos = []

        # 取得したアイテム数がlimitに達するまでループ
        page = 0
        while len(videos) < limit:
            # ページカウントを進める
            page += 1

            # ページを開く
            self.driver.get(f"https://ch.nicovideo.jp/{self.id}/video?page={page}")

            # 情報を取得
            videos.extend(self.__video_page())

            # 次のページがあるかどうかを確認
            for _ in range(30):
                next_buttons: list = self.driver.find_elements(By.XPATH, '//li[@class="next"]/a')
                next_disableds: list = self.driver.find_elements(By.XPATH, '//li[@class="next disabled"]')
                if next_buttons or next_disableds:
                    break
            else:
                raise  # FIXME

        # 結果を返す
        return videos

    def __video_page(self) -> list[Video]:
        videos = []
        item: WebElement

        # 投稿者の名前とIDを取得
        icon_link: WebElement = get_matching_element(base=self.driver, tag="span", attribute="class", pattern=r"^.*thumb_wrapper_ch.*$")
        poster_name: str = icon_link.find_element(By.XPATH, "./a").get_attribute("title")
        poster_id: str = icon_link.find_element(By.XPATH, "./a").get_attribute("href").split("/")[-1]

        # アイテムを取得
        items = WebDriverWait(self.driver, 20).until(EC.presence_of_all_elements_located((By.XPATH, '//li[@class="item"]')))
        # 動画情報を取得
        for item in items:
            # URL
            url: str = item.find_element(By.XPATH, ".//a").get_attribute("href")
            # 動画ID
            id: str = url.split("/")[-1]
            # タイトル
            title: str = item.find_element(By.XPATH, ".//h6/a").get_attribute("title")
            # サムネイル
            thumbnail: str = item.find_element(By.XPATH, ".//img").get_attribute("src")
            # 投稿日時
            posted_at: str = item.find_element(By.XPATH, './/p[@class="time"]/time/var').get_attribute("title")
            posted_at: datetime = datetime.strptime(posted_at, "%Y/%m/%d %H:%M")
            # 再生回数
            try:
                view_count: int = int(item.find_element(By.XPATH, './/li[@class="view "]/var').text.replace(",", ""))
            except NoSuchElementException:
                view_count = 0
            # コメント数
            try:
                comment_count: int = int(item.find_element(By.XPATH, './/li[@class="comment "]/var').text.replace(",", ""))
            except NoSuchElementException:
                comment_count = 0
            # マイリスト数
            try:
                my_list_count: int = int(item.find_element(By.XPATH, './/li[@class="mylist "]//var').text.replace(",", ""))
            except NoSuchElementException:
                my_list_count = 0
            # 再生時間
            minute, second = item.find_element(By.XPATH, './/span[@class="badge br length"]').text.split(":")
            duration: timedelta = timedelta(minutes=int(minute), seconds=int(second))
            duration: int = int(duration.total_seconds())

            # 動画情報を追加
            video = NicoNicoVideo(id)
            video.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                title=title,
                url=url,
                thumbnail=thumbnail,
                posted_at=posted_at.isoformat(),
                view_count=view_count,
                comment_count=comment_count,
                my_list_count=my_list_count,
                duration=duration,
            )
            videos.append(video)

        return videos

    # トップページのニュースを取得する
    def get_news(self, limit: int = 5) -> list[NicoNicoChannel.News]:
        """チャンネルのニュースコンテンツを取得"""
        newses = self.__fetch_news_feed(limit)
        return newses

    def __fetch_news_feed(self, limit: int) -> list[NicoNicoChannel.News]:
        """チャンネルのニュースをfeedを使って取得する"""
        newses = []

        # RSSフィードを取得
        feed = feedparser.parse(f"https://ch.nicovideo.jp/{self.id}/blomaga/nico/feed")

        # フィードのステータスを確認
        if feed["status"] > 400 or feed["bozo"] != False:
            raise Exception("feed err")  # FIXME: 例外を作成する

        # ニュースのアイテムを取得
        for entry in feed["entries"]:
            id = entry["id"].split("/")[-1]
            poster_id = self.id
            poster_name = entry["id"].split("/")[-3]
            title = entry["title"]
            url = entry["link"]
            thumbnail = entry["nicoch_article_thumbnail"]
            posted_at: datetime = datetime.strptime(entry["published"], "%a, %d %b %Y %H:%M:%S %z")  # ex:'Fri, 16 Jun 2023 12:00:00 +0900'

            # ニュース情報を追加
            news = NicoNicoChannel.News(poster_id, id)
            news.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                title=title,
                url=url,
                thumbnail=thumbnail,
                posted_at=posted_at.isoformat(),
            )
            # 取得したアイテム数がlimitに達したらループを抜ける
            if len(newses) >= limit:
                break

        return newses

    @execute_time()
    class News(News):
        """ニュースの情報を管理するクラス"""

        def __init__(self, poster_id: str, id: str) -> None:
            """他のコンテンツと違い、ニュースはIDと投稿者IDが必要"""
            check_channel_id(poster_id)
            check_news_id(id)
            super().__init__(id)
            self.poster_id = poster_id

        @classmethod
        def from_id(cls, poster_id: str, id: str) -> NicoNicoChannel.News:
            """IDからニュース情報を取得する"""
            news = cls(poster_id, id)
            news.get_detail()
            return news

        def get_detail(self) -> None:
            # ページを取得
            res = requests.get(f"https://ch.nicovideo.jp/{self.poster_id}/blomaga/{self.id}")

            # ステータスコードを確認
            if res.status_code >= 400:
                raise Exception("status code err")  # FIXME

            # BS4でパース
            soup = BeautifulSoup(res.text, "html.parser")

            # JSON-LDタグを取得 <script type="application/ld+json">
            json_ld = soup.find("script", type="application/ld+json").string
            json_ld = json.loads(json_ld)[0]

            # 投稿者ID
            poster_id: str = json_ld["image"]["url"].split("/")[-2]
            # ニュースID
            id: str = json_ld["mainEntityOfPage"].split("/")[-1]
            # タイトル
            title: str = json_ld["headline"]
            # URL
            url: str = f"https://ch.nicovideo.jp/{poster_id}/blomaga/{id}"
            # サムネイル
            thumbnail: str = json_ld["image"]["url"] if "image" in json_ld else ""
            # 投稿日時
            posted_at_text: str = json_ld["datePublished"]  # ex:"2023-09-16 19:03:00"
            posted_at: datetime = datetime.strptime(posted_at_text, "%Y-%m-%d %H:%M:%S")
            # 更新日時
            if "dateModified" in json_ld:
                updated_at_text: str = json_ld["dateModified"]  # ex:"2023-09-16 23:13:17"
                updated_at: datetime = datetime.strptime(updated_at_text, "%Y-%m-%d %H:%M:%S")
            else:
                updated_at = None
            # 内容
            body: str = soup.find("div", attrs={"class": "main_blog_txt"}).text

            # ニュース情報を設定
            self.poster_id = poster_id
            self.update_value(
                poster_id=poster_id,
                title=title,
                url=url,
                thumbnail=thumbnail,
                posted_at=posted_at.isoformat(),
                updated_at=updated_at.isoformat() if updated_at else None,
                body=body,
            )

            return None


@execute_time()
class NicoNicoLive(Live, ScrapingMixin):
    """生放送の情報を管理するクラス"""

    @classmethod
    def from_id(cls, id: str) -> NicoNicoLive:
        """IDから生放送情報を取得する"""
        check_live_id(id)
        live = cls(id)
        live.get_detail()
        return live

    def get_detail(self) -> None:
        """生放送の詳細情報をスクレイピングで取得する"""
        # ページを開く
        self.driver.get(f"https://live.nicovideo.jp/watch/{self.id}")

        # JSON-LDタグを取得
        json_ld: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//script[@type="application/ld+json"]')))
        json_ld: str = json_ld.get_attribute("innerHTML")
        json_ld: str = json.loads(json_ld)

        # URL
        url: str = json_ld["embedUrl"]
        # ID
        id: str = url.split("/")[-1]
        # 投稿者のURL
        author_url: list = json_ld["author"]["url"].split("/")
        # ユーザーIDまたはチャンネルID
        poster_id: str = author_url[-2] if author_url[-1] == "join" else author_url[-1]
        # チャンネルコンテンツか否か
        is_channel_content: str = author_url[-1] == "join"
        # タイトル
        title: str = json_ld["publication"]["name"]
        # サムネイル
        thumbnail: str = json_ld["thumbnailUrl"][0]
        # タグ
        tags: list = json_ld["keywords"]
        # 説明文
        description: WebElement = get_matching_element(base=self.driver, tag="div", attribute="class", pattern=r"^___description___.*$")
        description: str = description.text

        # 生放送の種類を判別（放送予定、放送中、過去放送）
        status, is_timeshift_enabled = self.__get_status()

        # 開始時間
        start_at: str = json_ld["publication"]["startDate"]
        start_at: datetime = datetime.fromisoformat(start_at)

        # 過去放送の場合
        if status == "past":
            end_at: str = json_ld["publication"]["endDate"]
            end_at: datetime = datetime.fromisoformat(end_at)
            duration: timedelta = end_at - start_at
            duration: int = int(duration.total_seconds())

        # タイムシフトが有効な場合
        if is_timeshift_enabled:
            timeshift_limit_at: WebElement = get_matching_element(base=self.driver, tag="time", attribute="class", pattern=r"^___program-viewing-period-date-time___.*$")
            timeshift_limit_at: str = timeshift_limit_at.get_attribute("datetime")
            timeshift_limit_at: datetime = datetime.strptime(timeshift_limit_at, "%Y-%m-%d %H:%M:%S")

        # 放送の開始時間、終了時間、長さ(過去放送のみ)
        if status == "past":
            start_at = json_ld["publication"]["startDate"]  # ISO8601形式
            end_at = json_ld["publication"]["endDate"]

        # 生放送オブジェクトを作成
        self.id = id
        self.url = url
        self.poster_id = poster_id
        self.title = title
        self.thumbnail = thumbnail
        self.tags = tags
        self.description = description
        self.status = status
        self.start_at = start_at.isoformat()
        if status == "past":
            self.end_at = end_at.isoformat()
            self.duration = duration
        if is_timeshift_enabled:
            self.archive_enabled_at = timeshift_limit_at.isoformat()

        return None

    def __get_status(self) -> tuple[str, bool]:
        """生放送の状態を判別する"""
        status: str
        is_timeshift_enabled: bool = False

        # タイムシフトの公開期間を取得
        timeshift_element = get_matching_element(base=self.driver, tag="time", attribute="class", pattern=r"^___program-viewing-period-date-time___.*$")
        # 動画上に表示されるメッセージを取得
        message_element = get_matching_element(base=self.driver, tag="p", attribute="class", pattern=r"^___primary-message___.*$")
        # LIVE中のボタンを取得
        live_button: list = self.driver.find_elements(By.XPATH, '//button[@data-live-status="live"]')

        # 分類
        if timeshift_element:
            status = "past"
            is_timeshift_enabled = True
        elif message_element.text == "放送開始までしばらくお待ちください":
            status = "future"
        elif message_element.text == "タイムシフトの公開期間が終了しました":
            status = "past"
            is_timeshift_enabled = False
        elif live_button:
            status = "now"
        return status, is_timeshift_enabled


@execute_time()
class NicoNicoVideo(Video):
    """動画の情報を管理するクラス"""

    @classmethod
    def from_id(cls, id: str) -> NicoNicoVideo:
        """IDから動画情報を取得する"""
        check_video_id(id)
        video = cls(id)
        video.get_detail()
        return video

    def get_detail(self) -> None:
        """動画APIから情報を取得する"""
        # 動画情報を取得
        res = requests.get(f"https://ext.nicovideo.jp/api/getthumbinfo/{self.id}")
        # ステータスコードを確認
        if res.status_code > 400:
            raise Exception("status code err")  # FIXME

        # テキストに変換
        res.text.encode("utf-8")

        # # XMLを保存
        # with open(f"{self.id}.xml", mode="w", encoding="utf-8") as f:
        #     f.write(res.text)

        # ElementTreeに変換
        root = ET.fromstring(res.text)

        # 削除されているか
        if not root.attrib["status"] == "ok":
            self.is_deleted = True
            return None

        # ID
        id: str = root.find(".//video_id").text
        # 投稿者名とID
        if root.find(".//ch_id") is not None:
            poster_id: str = root.find(".//ch_id").text
            poster_name: str = root.find(".//ch_name").text
        else:
            poster_id: str = root.find(".//user_id").text
            poster_name: str = root.find(".//user_nickname").text
        # タイトル
        title: str = root.find(".//title").text
        # URL
        url: str = root.find(".//watch_url").text
        # サムネイル
        thumbnail: str = root.find(".//thumbnail_url").text
        # 公開日時
        posted_at: str = root.find(".//first_retrieve").text
        posted_at: datetime = datetime.fromisoformat(posted_at)
        # 再生時間
        length_text: str = root.find(".//length").text
        minute, second = length_text.split(":")
        duration: timedelta = timedelta(minutes=int(minute), seconds=int(second))
        duration: int = int(duration.total_seconds())
        # 再生数
        view_count: int = int(root.find(".//view_counter").text)
        # コメント数
        comment_count: int = int(root.find(".//comment_num").text)
        # マイリスト数
        my_list_count: int = int(root.find(".//mylist_counter").text)
        # タグ
        tags = []
        for tag in root.findall(".//tags/tag"):
            tags.append(tag.text)
        # 説明文
        description: str = root.find(".//description").text

        # 動画情報を設定
        self.id = id
        self.update_value(
            poster_id=poster_id,
            poster_name=poster_name,
            title=title,
            url=url,
            thumbnail=thumbnail,
            posted_at=posted_at.isoformat(),
            view_count=view_count,
            comment_count=comment_count,
            my_list_count=my_list_count,
            duration=duration,
            tags=tags,
            description=description,
        )

        return None


# チャンネルIDがパターンに一致しない場合例外を発生させる
@staticmethod
def check_channel_id(channel_id: str):
    if not re.match(CHANNEL_ID_PATTERN, channel_id):
        raise InvalidChannelIdPatternError(channel_id)


# 生放送IDがパターンに一致しない場合例外を発生させる
@staticmethod
def check_live_id(live_id: str):
    if not re.match(LIVE_ID_PATTERN, live_id):
        raise InvalidLiveIdPatternError(live_id)


# 動画IDがパターンに一致しない場合例外を発生させる
@staticmethod
def check_video_id(video_id: str):
    if not re.match(VIDEO_ID_PATTERN, video_id):
        raise InvalidVideoIdPatternError(video_id)


# ニュースIDがパターンに一致しない場合例外を発生させる
@staticmethod
def check_news_id(news_id: str):
    if not re.match(NEWS_ID_PATTERN, news_id):
        raise InvalidNewsIdPatternError(news_id)


# チャンネルIDの形式が不正な場合の例外
class InvalidChannelIdPatternError(Exception):
    def __init__(self, video_id):
        super().__init__(f"Invalid video ID: {video_id}")


# 生放送IDの形式が不正な場合の例外
class InvalidLiveIdPatternError(Exception):
    def __init__(self, live_id):
        super().__init__(f"Invalid live id. ID: {live_id}")


# 動画IDの形式が不正な場合の例外
class InvalidVideoIdPatternError(Exception):
    def __init__(self, video_id):
        super().__init__(f"Invalid video ID: {video_id}")


# ニュースIDの形式が不正な場合の例外
class InvalidNewsIdPatternError(Exception):
    def __init__(self, news_id):
        super().__init__(f"Invalid news ID: {news_id}")
