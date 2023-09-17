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

from .base_class import ScrapingClass, Platform, Content, Live, Video, News
from .common_func import get_matching_element, get_matching_all_elements, parse_video_duration
from my_utilities.debug import execute_time


logger = logging.getLogger(__name__)

root_xpath: str = '//div[@id="root"]'
header_xpath: str = '//div[@id="root"]/div/div[1]'
main_xpath: str = '//div[@id="root"]/div/div[2]/div[1]'
footer_xpath: str = '//div[@id="root"]/div/div[2]/div[2]'
not_found_xpath: str = '//h5[text()="ページを表示することができませんでした"]'
not_found_xpath2: str = '//h5[text()="お探しのページは見つかりませんでした"]'


@execute_time()
class ChannelPlusChannel(ScrapingClass):
    """ニコニコチャンネルプラスのコンテンツを取得するクラス"""

    def __init__(self, channel_name: str) -> None:
        super().__init__(channel_name)

    # トップページの全てのコンテンツを取得する
    def get_all(self, limit_video: int = 0, limit_news: int = 0) -> dict:
        lives = self.get_live(limit=limit_live)
        videos = self.get_video(limit=limit_video)
        newses = self.get_news(limit=limit_news)

        return lives, videos, newses

    # トップページの生放送を取得する
    def get_live(self) -> list[ChannelPlusLive]:
        lives = self.__live_page()
        return lives

    def __live_page(self) -> list[ChannelPlusLive]:
        """ニコニコチャンネルプラスの生放送ページから配信中の放送と放送予定を取得するメソッド"""
        lives = []

        # 生放送ページを開く
        self.driver.get(f"https://nicochannel.jp/{self.id}/lives")

        # セクションを取得出来るまでリトライ
        start = time.time()
        while True:
            sections: list = self.driver.find_elements(By.XPATH, f"{main_xpath}/div/div")
            if len(sections) >= 2:
                break
            if time.time() - start > 20:
                raise  # FIXME: 例外処理をちゃんとする

        # 生放送のリストを取得
        lives = []
        if len(sections) == 3:
            lives.extend(self.__get_from_now_section(sections[0]))
            lives.extend(self.__get_from_future_section(sections[1]))
        else:
            lives.extend(self.__get_from_future_section(sections[0]))

        # 結果を返す
        return lives

    def __get_from_now_section(self, now_section: WebElement) -> list[ChannelPlusLive]:
        # TODO
        return []

    def __get_from_future_section(self, future_section: WebElement) -> list[ChannelPlusLive]:
        """放送予定の生放送情報を取得する"""
        # アイテムの取得  //*[@id="app-layout"]/div[2]/div[1]/div[1]/div/div/div/div/a
        items = get_matching_all_elements(base=future_section, tag="a", attribute="class", pattern=r"^MuiButtonBase-root MuiCardActionArea-root.*$")
        if not items:
            return []

        lives = []
        for item in items:
            live = self.__future_item(item)
            lives.append(live)

        return lives

    def __future_item(self, item: WebElement) -> ChannelPlusLive:
        # チャンネルID
        # TODO
        # タイトル
        title: str = item.find_element(By.XPATH, "div[2]/div[1]/h6").text
        # 状態
        status: str = "future"
        # リンク
        url: str = item.get_attribute("href")
        # ID
        id: str = url.split("/")[-1]
        # サムネイル
        thumbnail: str = item.find_element(By.XPATH, "div").get_attribute("style")
        thumbnail: str = re.search(r"https.*(\d+)", thumbnail).group()
        # 開始予定時刻 ex:'09/16 21:00', '今日 21:00' etc...
        start_at: WebElement = get_matching_element(base=item, tag="span", attribute="class", pattern=r"^.*MuiTypography-caption.*$")
        start_at: str = start_at.text
        try:
            start_at: datetime = datetime.strptime(start_at, "%m/%d %H:%M")
        except:  # FIXME: 例外処理をちゃんとする
            time_ = start_at[-5:]  # 後ろの時間部分を取得
            hour, minute = time_.split(":")  # 時間部分を取得
            if "今日" in start_at:
                now: datetime = datetime.now()
                start_at: datetime = now.replace(hour=int(hour), minute=int(minute))
            elif "明日" in start_at:
                tommorow: datetime = datetime.now() + timedelta(days=1)
                start_at: datetime = tommorow.replace(hour=int(hour), minute=int(minute))

        # TODO

    # トップページの動画を取得する
    def get_video(self, type_: str = "upload") -> list[ChannelPlusVideo]:
        videos = self.__video_page(type_)
        return videos

    def __video_page(self, type_: str) -> list[ChannelPlusVideo]:
        """ニコニコチャンネルプラスの動画ページをスクレイピングする"""
        # 動画ページを開く
        self.driver.get(f"https://nicochannel.jp/{self.id}/videos")

        # 指定されたタイプのボタンをクリックして遷移
        if type_ == "upload":
            uploaded_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, '//span[text()="アップロード動画"]/..')))
            uploaded_btn.click()
        elif type_ == "archive":
            archive_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, '//span[text()="アーカイブ動画"]/..')))
            archive_btn.click()
        elif type_ == "all":
            pass
        else:
            raise ValueError("type must be 'upload' or 'archive' or 'all'")

        # 一番下にたどり着くまでスクロール
        while True:
            # 現在のスクロール位置を取得
            current_position: int = self.driver.execute_script("return window.pageYOffset")
            # スクロール
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # スクロールが終わるまで待機
            self.wait.until(EC.presence_of_element_located((By.XPATH, f"{footer_xpath}")))
            # 現在のスクロール位置を取得
            new_position: int = self.driver.execute_script("return window.pageYOffset")
            # スクロールが終わったらループを抜ける
            if current_position == new_position:
                break

        # アイテムを取得
        main: WebElement = self.driver.find_element(By.XPATH, '//div[@id="root"]/div/div[2]/div[1]')
        items: list = get_matching_all_elements(base=main, tag="div", attribute="class", pattern=r"^.*MuiGrid-item.*$")
        if not items:
            return []

        # 各アイテムから動画情報を取得
        videos = []
        for item in items:
            video = self.__video_item(item)
            videos.append(video)

        return videos

    def __video_item(self, item: WebElement) -> ChannelPlusVideo:
        item_upper: WebElement = item.find_element(By.XPATH, "./div/div/div[1]")
        item_under: WebElement = item.find_element(By.XPATH, "./div/div/div[2]")
        # 投稿者ID
        # TODO
        # タイトル
        title: str = item_under.find_element(By.XPATH, ".//h6").text
        # リンク
        url: str = item_under.find_element(By.XPATH, ".//a").get_attribute("href")
        # ID
        id: str = url.split("/")[-1]
        # サムネイル
        thumbnail: str = item_upper.find_element(By.XPATH, ".//img").get_attribute("src")
        # 投稿日時
        posted_at: str = item_under.find_element(By.XPATH, ".//span").text  # ex:"2023/07/06", "〇日前"
        try:
            posted_at: datetime = datetime.strptime(posted_at, "%Y/%m/%d")
        except:  # FIXME: 例外処理をちゃんとする
            before_days: int = int(posted_at[0])
            posted_at: datetime = datetime.now() - timedelta(days=before_days)
        # 動画時間
        length: str = item_upper.find_element(By.XPATH, "./div[2]").text  # 00:00:00
        length: timedelta = parse_video_duration(length)
        # 再生数
        view_count: WebElement = item_under.find_element(By.XPATH, "./div/div/div[1]/div")
        view_count: int = int(view_count.text)
        # コメント数
        comment_count: WebElement = item_under.find_element(By.XPATH, "./div/div/div[2]/div")
        comment_count: int = int(comment_count.text)

        # TODO

    # トップページのニュースを取得する
    def get_news(self, limit: int = 0) -> list[ChannelPlusNews]:
        newses = self.__news_page(limit=limit)
        return newses

    def __news_page(self, limit) -> list[ChannelPlusNews]:
        # ニュースページを開く
        self.driver.get(f"https://nicochannel.jp/{self.id}/articles/news")

        # 一番下にたどり着くまでスクロール
        while True:
            # 現在のスクロール位置を取得
            current_position: int = self.driver.execute_script("return window.pageYOffset")
            # スクロール
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # スクロールが終わるまで待機
            self.wait.until(EC.presence_of_element_located((By.XPATH, f"{footer_xpath}")))
            # 現在のスクロール位置を取得
            new_position: int = self.driver.execute_script("return window.pageYOffset")
            # スクロールが終わったらループを抜ける
            if current_position == new_position:
                break

        # メインの要素を取得 FIXME
        main = self.wait.until(EC.presence_of_element_located((By.XPATH, self.main_xpath)))

        # アイテムを取得
        items = get_matching_all_elements(base=main, tag="div", attribute="class", pattern=r"^.*MuiPaper-rounded.*$")
        if not items:
            return []

        # 各ニュースから情報を取得
        newses = []
        for item in items:
            news = self.__news_item(item)
            newses.append(news)

        # 結果を返す
        return newses

    def __news_item(self, item: WebElement) -> ChannelPlusNews:
        # 投稿者ID
        # TODO
        # タイトル
        title: str = item.find_element(By.XPATH, ".//h6").text
        # サムネイル
        thumbnail: str = item.find_element(By.XPATH, ".//img").get_attribute("src")
        # 投稿日時
        posted_at: str = item.find_element(By.XPATH, "./div[2]/div[3]/div").text  # ex:"2023/07/06","〇日前","〇時間前"
        try:
            posted_at: datetime = datetime.strptime(posted_at, "%Y/%m/%d")
        except:  # FIXME: 例外処理をちゃんとする
            if "日前" in posted_at:
                before_days: int = int(posted_at[0])
                posted_at: datetime = datetime.now() - timedelta(days=before_days)
            elif "時間前" in posted_at:
                before_hours: int = int(posted_at[0])
                posted_at: datetime = datetime.now() - timedelta(hours=before_hours)

        # ニュースページを開いて詳細情報を取得 TODO


class ChannelPlusVideo(Video):
    """ニコニコチャンネルプラスの動画情報を格納するクラス"""

    def __init__(self, poster_id: str, id: str) -> None:
        super().__init__(id)
        self.poster_id = poster_id

    @classmethod
    def from_id(cls, id: str) -> ChannelPlusVideo:
        video = cls(id)
        video.get_detail()
        return video

    def get_detail(self) -> None:
        # コンテンツページを開いて詳細情報を取得
        video = __content_page(self, self.driver, self.poster_id, self.id)
        # 詳細情報を格納
        self.title = video["title"]
        self.url = video["url"]
        self.id = video["id"]
        self.poster_id = video["poster_id"]
        self.thumbnail = video["thumbnail"]
        self.description = video["description"]

        return None


class ChannelPlusLive(Live):
    """ニコニコチャンネルプラスの生放送情報を格納するクラス"""

    def __init__(self, poster_id: str, id: str) -> None:
        super().__init__(id)
        self.poster_id = poster_id

    @classmethod
    def from_id(cls, id: str) -> ChannelPlusVideo:
        live = cls(id)
        live.get_detail()
        return live

    def get_detail(self) -> None:
        # コンテンツページを開いて詳細情報を取得
        live = __content_page(self, self.driver, self.poster_id, self.id)
        # 詳細情報を格納
        self.title = live["title"]
        self.url = live["url"]
        self.id = live["id"]
        self.poster_id = live["poster_id"]
        self.thumbnail = live["thumbnail"]
        self.description = live["description"]

        return None


class ChannelPlusNews(News):
    """ニコニコチャンネルプラスのニュース情報を格納するクラス"""

    def __init__(self, poster_id: str, id: str) -> None:
        super().__init__(id)
        self.poster_id = poster_id


# ニコニコチャンネルプラスのコンテンツページをスクレイピングする
def __content_page(self, driver: webdriver.Chrome, poster_id: str, id: str) -> dict:
    """ニコニコチャンネルプラスのコンテンツページをスクレイピングする"""
    # コンテンツのページを開く
    driver.get(f"https://nicochannel.jp/{poster_id}/live/{id}")

    # メインの要素を取得 FIXME
    main: WebElement = self.wait.until(EC.presence_of_element_located((By.XPATH, self.main_xpath)))

    # タイトル
    title: str = main.find_element(By.XPATH, '/html/head/meta[@property="og:title"]').get_attribute("content")
    # URL FIXME
    url: str = driver.current_url
    # ID
    id: str = url.split("/")[-1]
    # 投稿者ID
    poster_id: str = url.split("/")[-3]
    # サムネイル
    thumbnail: str = main.find_element(By.XPATH, '/html/head/meta[@property="og:image"]').get_attribute("content")
    # 説明文
    description: str = main.find_element(By.XPATH, '/html/head/meta[@name="description"]').get_attribute("content")

    # ラベルからコンテンツの種類と状態を取得
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//div[@id="video-page-wrapper"]')))
    labels: list = main.find_elements(By.XPATH, '//span[@class="MuiChip-label MuiChip-labelSmall"]')
    for label in labels:
        # TODO
        pass

    result = {
        "title": title,
        "url": url,
        "id": id,
        "poster_id": poster_id,
        "thumbnail": thumbnail,
        "description": description,
    }

    return result
