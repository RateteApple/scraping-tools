# coding: utf-8

from __future__ import annotations
from datetime import datetime, timedelta
import re

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


# コンテンツクラス
class Content:
    """コンテンツクラス

    コンテンツの情報を格納する
    """

    title: str
    url: str
    thumbnail: str
    posted_at: datetime
    platform: str
    poster_name: str
    poster_id: str

    def __init__(
        self,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: datetime = None,
        platform: str = None,
        poster_name: str = None,
        poster_id: str = None,
    ):
        """初期化関数

        コンテンツの情報を初期化する
        """
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.posted_at = posted_at
        self.platform = platform
        self.poster_name = poster_name
        self.poster_id = poster_id

    def __str__(self):
        """文字列化関数

        コンテンツの情報を文字列化する
        """
        return f"Title: {self.title}, URL: {self.url}, PostedAt: {self.posted_at}"


# 動画クラス
class Video(Content):
    """動画クラス

    動画の情報を格納する
    """

    duration: timedelta
    view_count: int
    like_count: int
    dislike_count: int
    comment_count: int
    tags: list[str]

    def __init__(
        self,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: datetime = None,
        platform: str = None,
        poster_name: str = None,
        poster_id: str = None,
        duration: timedelta = None,
        view_count: int = None,
        like_count: int = None,
        dislike_count: int = None,
        comment_count: int = None,
        tags: list[str] = None,
    ):
        """初期化関数

        動画の情報を初期化する
        """
        super().__init__(title, url, thumbnail, posted_at, platform, poster_name, poster_id)
        self.duration = duration
        self.view_count = view_count
        self.like_count = like_count
        self.dislike_count = dislike_count
        self.comment_count = comment_count
        self.tags = tags
        """文字列化関数

        動画の情報を文字列化する
        """
        super().__str__()


# 生放送クラス
class Live(Content):
    """生放送クラス

    生放送の情報を格納する
    """

    duration: timedelta
    tags: list[str]
    scduled_start_at: datetime
    actual_start_at: datetime
    scduled_end_at: datetime
    actual_end_at: datetime
    current_view_count: int

    def __init__(
        self,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: datetime = None,
        platform: str = None,
        poster_name: str = None,
        poster_id: str = None,
        duration: timedelta = None,
        tags: list[str] = None,
        scduled_start_at: datetime = None,
        actual_start_at: datetime = None,
        scduled_end_at: datetime = None,
        actual_end_at: datetime = None,
        current_view_count: int = None,
    ):
        """初期化関数

        生放送の情報を初期化する
        """
        super().__init__(title, url, thumbnail, posted_at, platform, poster_name, poster_id)
        self.duration = duration
        self.tags = tags
        self.scduled_start_at = scduled_start_at
        self.actual_start_at = actual_start_at
        self.scduled_end_at = scduled_end_at
        self.actual_end_at = actual_end_at
        self.current_view_count = current_view_count


# ニュースクラス
class News(Content):
    """ニュースクラス

    ニュースの情報を格納する
    """

    body: str

    def __init__(
        self,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: datetime = None,
        platform: str = None,
        poster_name: str = None,
        poster_id: str = None,
        body: str = None,
    ):
        """初期化関数

        ニュースの情報を初期化する
        """
        super().__init__(title, url, thumbnail, posted_at, platform, poster_name, poster_id)
        self.body = body


# 年部分を補完する関数
def set_year(object: datetime) -> datetime:
    """現在日時とdatetimeオブジェクトの月日から年を推測して設定する"""
    # 月部分を比較して年を設定する
    now = datetime.now()
    if object.month < now.month:
        # 月が現在より小さい場合は来年にする
        object = object.replace(year=now.year + 1)
    else:
        # 月が現在と同じか大きい場合は今年にする
        object = object.replace(year=now.year)

    return object


# 正規表現に一致する要素を1つ取得する関数
def get_matching_element(base_element: WebElement, tag: str, attribute: str, pattern: re.Pattern) -> WebElement:
    """正規表現に一致する要素を取得する

    一致する要素がない場合はNoneを返す"""
    element: WebElement
    match_element = None

    # 要素を全て取得
    elements: list = base_element.find_elements(By.XPATH, f".//{tag}")
    # 正規表現に一致する要素のみを抽出
    for element in elements:
        try:
            attribute_value: str = element.get_attribute(attribute)
            if pattern.match(attribute_value):
                match_element = element
                break
        except StaleElementReferenceException:
            continue

    # 要素を返す
    return match_element


# 正規表現に一致する要素を全て取得する関数
def get_matching_all_elements(base_element: WebElement, tag: str, attribute: str, pattern: re.Pattern) -> list[WebElement]:
    """正規表現に一致する要素を全て取得する"""
    element: WebElement
    match_elements = []

    # 要素を全て取得
    try:
        elements: list = base_element.find_elements(By.XPATH, f".//{tag}")
    except StaleElementReferenceException:
        return []

    # 正規表現に一致する要素のみを抽出
    for element in elements:
        try:
            attribute_value: str = element.get_attribute(attribute)
            if pattern.match(attribute_value):
                match_elements.append(element)
        except StaleElementReferenceException:
            continue

    # 要素を返す
    return match_elements


# 動画時間文字列を時間、分、秒に分割する関数
def parse_video_duration(duration_str: str) -> timedelta:
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
        raise Exception("引数の形式が不正です")

    # timedelta オブジェクトを作成
    video_duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)

    return video_duration
