# coding: utf-8

from __future__ import annotations
from datetime import datetime, timedelta
import re
from pprint import pformat
from typing import Any
import unicodedata

from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


class ScrapingClass(object):
    is_headless: bool = True
    timeout: int = 20

    def __del__(self) -> None:
        # ブラウザを閉じる
        self.close_browser()

    def __getattr__(self, name: str) -> None:
        """ブラウザが開かれていない場合にブラウザを開く"""
        if name == "driver":
            self.open_browser()
            return self.driver

    def set_browser_settings(self, is_headless: bool = True, timeout: int = 20) -> None:
        """ブラウザの設定を変更する

        設定はクラス変数に保存されるため、インスタンス生成前にコールすること。"""

        self.is_headless = is_headless
        self.timeout = timeout

    @classmethod
    def set_browser_settings_all(cls, is_headless: bool = True, timeout: int = 20) -> None:
        """全てのクラスのブラウザ設定を変更する

        設定はクラス変数に保存されるため、インスタンス生成前にコールすること。"""

        cls.is_headless = is_headless
        cls.timeout = timeout

    def open_browser(self, is_headless: bool = None, timeout: int = None) -> None:
        """ブラウザを開く

        オプションを指定しなかった場合はクラス変数の値を使用する
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")  # 保護機能を無効化
        options.add_argument("--disable-gpu")  # GPUの使用を無効化
        options.add_argument("--window-size=1920,1080")  # Windowサイズを1920x1080に設定
        options.add_experimental_option("excludeSwitches", ["enable-logging"])  # ログを無効化
        options.add_argument("--blink-settings=imagesEnabled=false")  # 画像を読み込まない
        options.add_argument("--disable-extensions")  # 拡張機能を無効化

        if not is_headless:
            is_headless = self.__class__.is_headless
        if not timeout:
            timeout = self.__class__.timeout

        if is_headless:
            options.add_argument("--headless")

        self.driver = webdriver.Chrome(options)
        self.wait = WebDriverWait(self.driver, self.timeout)

        return self.driver

    def close_browser(self) -> None:
        """ブラウザを閉じる"""
        # インスタンス変数にブラウザが存在する場合は閉じる
        if hasattr(self, "driver"):
            self.driver.quit()


class Platform(ScrapingClass):
    def __init__(self, id: str) -> None:
        self.id = id


class Content(ScrapingClass):
    """コンテンツの基底クラス"""

    id: str
    poster_id: str
    poster_name: str
    title: str
    url: str
    thumbnail: str
    posted_at: datetime
    updated_at: datetime
    tags: list[str]
    is_deleted: bool

    def __init__(self, id: str) -> None:
        self.id: str = id
        self.poster_id: str = ""
        self.poster_name: str = ""
        self.title: str = ""
        self.url: str = ""
        self.thumbnail: str = ""
        self.posted_at: datetime = None
        self.updated_at: datetime = None
        self.tags: list[str] = []
        self.is_deleted: bool = False

    def __str__(self) -> str:
        return f"ID: {self.id}, Title: {self.title}, URL: {self.url}"

    def __repr__(self) -> str:
        # is_headlessとtimeoutを除外
        result = {}
        for key, value in vars(self).items():
            if key in ["is_headless", "timeout"]:
                continue
            result[key] = value

        return pformat(result)

    def __setattr__(self, __name: str, __value: Any) -> None:
        # datetime型
        if __name == "posted_at" or __name == "updated_at":
            if isinstance(__value, str) and __value:
                __value = datetime.fromisoformat(__value)
        # タイトル
        elif __name == "title":
            __value = unicodedata.normalize("NFKC", __value)

        super().__setattr__(__name, __value)

    @classmethod
    def from_dict(cls, dict: dict) -> Content:
        """辞書からインスタンスを生成する"""
        # インスタンスを生成
        instance = cls(dict["id"])
        # 属性を設定
        for key, value in dict.items():
            setattr(instance, key, value)

        # インスタンスを返す
        return instance

    def to_dict(self) -> dict:
        result = {}
        # 属性を取得
        for key, value in vars(self).items():
            # is_headlessとtimeoutは除外
            if key in ["is_headless", "timeout"]:
                continue
            result[key] = value

        return result

    @staticmethod
    def diff(base: object, target: object) -> dict:
        """2つのインスタンスを比較して変更点を返す"""
        # クラスが異なる場合はNotImplemented
        if not base.__class__.__name__ == target.__class__.__name__:
            return NotImplemented

        # 変更点を取得
        diffs = {}
        for key, value in target.__dict__.items():
            # str, int, float, bool, list, dict, tuple, None以外は除外
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                continue
            # 変更点がある場合は追加
            if base.__dict__[key] != value:
                diff = {key: (base.__dict__[key], value)}
                diffs.update(diff)

        # 結果を返す
        return diffs


class Video(Content):
    description: str
    duration: timedelta
    view_count: int
    like_count: int
    comment_count: int

    def __init__(self, id: str) -> None:
        super().__init__(id)
        self.description = ""
        self.duration = ""
        self.view_count = 0
        self.like_count = 0
        self.comment_count = 0

    def __setattr__(self, __name: str, __value: Any) -> None:
        # description
        if __name == "description":
            __value = unicodedata.normalize("NFKC", __value)

        super().__setattr__(__name, __value)


class Live(Content):
    start_at: datetime
    end_at: datetime
    status: str
    archive_enabled_at: datetime

    def __init__(self, id: str) -> None:
        super().__init__(id)
        self.start_at = ""
        self.end_at = ""
        self.status = ""
        self.archive_enabled_at = ""

    def __setattr__(self, __name: str, __value: Any) -> None:
        # datetime型
        if __name == "start_at" or __name == "end_at" or __name == "archive_enabled_at":
            if isinstance(__value, str) and __value:
                __value = datetime.fromisoformat(__value)

        super().__setattr__(__name, __value)


class News(Content):
    body: str

    def __init__(self, id: str) -> None:
        super().__init__(id)
        self.body = ""

    def __setattr__(self, __name: str, __value: Any) -> None:
        # body
        if __name == "body":
            __value = unicodedata.normalize("NFKC", __value)

        super().__setattr__(__name, __value)


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
