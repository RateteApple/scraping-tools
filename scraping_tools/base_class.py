# coding: utf-8

from __future__ import annotations
from datetime import datetime, timedelta
import re
import json
import os
import io
from PIL import Image
import requests
from pprint import pformat
from typing import Any
import unicodedata

from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


class ScrapingMixin(object):
    """スクレイピング用のミックスインクラス"""

    _driver: webdriver.Chrome
    _timeout: int = 20
    _wait: WebDriverWait
    _gui: bool = False
    _img_load: bool = False

    def open_browser(self) -> None:
        """ブラウザを開く

        環境変数SCRAPING_TOOLS_HEADLESS_MODEがTrueの場合はヘッドレスモードで起動する。
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")  # 保護機能を無効化
        options.add_argument("--disable-gpu")  # GPUの使用を無効化
        options.add_argument("--window-size=1920,1080")  # Windowサイズを1920x1080に設定
        options.add_experimental_option("excludeSwitches", ["enable-logging"])  # ログを無効化
        options.add_argument("--disable-extensions")  # 拡張機能を無効化
        # 画像読み込みの設定
        if not self._img_load:
            options.add_argument("--blink-settings=imagesEnabled=false")
        # ヘッドレスモードの設定
        if not self._gui:
            options.add_argument("--headless")
        # ブラウザを開く
        self._driver = webdriver.Chrome(options)
        # 待機時間を設定
        self._wait = WebDriverWait(self._driver, self._timeout)

        return self._driver

    def close_browser(self) -> None:
        """ブラウザを閉じる"""
        # インスタンス変数にブラウザが存在する場合は閉じる
        if "_driver" in self.__dict__:
            self._driver.quit()

    def __getattr__(self, name: str) -> None:
        """ブラウザが開かれていない場合にブラウザを開く"""
        if name == "_driver" and not "_driver" in self.__dict__:
            self.open_browser()
            return self._driver

    def __del__(self) -> None:
        # ブラウザを閉じる
        self.close_browser()


class Platform:
    def __init__(self, id: str) -> None:
        """チャンネルIDなどサイト毎の固有IDを設定する"""
        self.id = id


class Content:
    """コンテンツの基底クラス"""

    id: str
    poster_id: str
    poster_name: str
    poster_url: str
    title: str
    url: str
    thumbnail: str
    posted_at: str
    updated_at: str
    tags: list[str]
    is_deleted: bool

    def __init__(self, id: str) -> None:
        self.id: str = id
        self.poster_id: str = None
        self.poster_name: str = None
        self.poster_url: str = None
        self.title: str = None
        self.url: str = None
        self.thumbnail: str = None
        self.posted_at: str = None
        self.updated_at: str = None
        self.tags: list[str] = []
        self.is_deleted: bool = False

    def __str__(self) -> str:
        return f"「{self.title}」 URL:{self.url}"

    def __repr__(self) -> str:
        values: dict = vars(self)
        for key, value in values.items():
            # 長すぎる文字列は省略
            if isinstance(value, str) and len(value) > 120:
                values[key] = value[:120] + "..."
            # 長すぎるリストは省略
            elif isinstance(value, list) and len(value) > 8:
                values[key] = value[:8] + ["etc..."]

        return pformat(values)

    def __setattr__(self, __name: str, __value: Any) -> None:
        # strは正規化
        if isinstance(__value, str):
            __value = unicodedata.normalize("NFKC", __value)

        super().__setattr__(__name, __value)

    def __eq__(self, other: Content) -> bool:
        return self.id == other.id

    @classmethod
    def from_dict(cls, dict: dict) -> Content:
        # インスタンスを生成
        instance = cls(dict["id"])

        # 辞書の値をインスタンスに設定
        instance.set_value(**dict)

        return instance

    def to_dict(self) -> dict:
        # クラスの全ての属性名を取得
        all_attributes = dir(self)

        # メソッドを除外
        attributes = [attribute for attribute in all_attributes if not callable(getattr(self, attribute))]

        # "_"から始まる属性を除外
        attributes = [attribute for attribute in attributes if not attribute.startswith("_")]

        # 辞書に変換
        _dict = {attribute: getattr(self, attribute) for attribute in attributes}

        return _dict

    def diff(self, other: Content) -> dict:
        """他のインスタンスとの差分を取得する

        他のインスタンスとの差分を辞書で返す。
        """
        # クラスの全ての属性名を取得
        all_attributes = dir(self)

        # メソッドを除外
        attributes = [attribute for attribute in all_attributes if not callable(getattr(self, attribute))]

        # "_"から始まる属性を除外
        attributes = [attribute for attribute in attributes if not attribute.startswith("_")]

        # 差分を取得
        diff: list[dict[str, tuple]] = []
        for attribute in attributes:
            if getattr(self, attribute) != getattr(other, attribute):
                diff.append({attribute: (getattr(self, attribute), getattr(other, attribute))})

        return diff

    def get_thumbnail(self, *, size: tuple[int, int] = None) -> bytes:
        """URLからサムネイルを取得してバイナリで返す"""
        # サムネイルが存在する場合はそのまま返す
        if self.thumbnail is None:
            raise ValueError("サムネイルが設定されていません。")

        # サムネイルを取得
        res = requests.get(self.thumbnail)

        # リスポンスが200以外の場合は例外を発生
        if res.status_code != 200:
            raise Exception(f"Failed to get thumbnail. status_code: {res.status_code}")

        # widthとheightが指定されている場合はリサイズ
        if size is not None:
            # PIL.Imageに変換
            img = Image.open(io.BytesIO(res.content))

            # リサイズ
            resized_img = img.resize(size)

            # bytes型に変換
            img_bytes = io.BytesIO()
            resized_img.save(img_bytes, format="PNG")
            img_bytes = img_bytes.getvalue()

        else:
            img_bytes = res.content

        return img_bytes


class Video(Content):
    description: str
    duration: int
    view_count: int
    like_count: int
    comment_count: int

    def __init__(self, id: str) -> None:
        super().__init__(id)
        self.description = None
        self.duration = None
        self.view_count = None
        self.like_count = None
        self.comment_count = None

    def set_value(
        self,
        poster_id: str = None,
        poster_name: str = None,
        poster_url: str = None,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: str = None,
        updated_at: str = None,
        tags: list[str] = None,
        is_deleted: bool = None,
        description: str = None,
        duration: int = None,
        view_count: int = None,
        like_count: int = None,
        comment_count: int = None,
    ) -> None:
        """属性を設定する

        すべての属性を一度に設定することができる。
        """
        self.poster_id = poster_id
        self.poster_name = poster_name
        self.poster_url = poster_url
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.posted_at = posted_at
        self.updated_at = updated_at
        self.tags = tags
        self.is_deleted = is_deleted
        self.description = description
        self.duration = duration
        self.view_count = view_count
        self.like_count = like_count
        self.comment_count = comment_count

    def update_value(
        self,
        poster_id: str = None,
        poster_name: str = None,
        poster_url: str = None,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: str = None,
        updated_at: str = None,
        tags: list[str] = None,
        is_deleted: bool = None,
        description: str = None,
        duration: int = None,
        view_count: int = None,
        like_count: int = None,
        comment_count: int = None,
    ) -> None:
        """属性を更新する

        すべての属性を一度に更新することができる。
        """
        self.poster_id = poster_id if poster_id is not None else self.poster_id
        self.poster_name = poster_name if poster_name is not None else self.poster_name
        self.poster_url = poster_url if poster_url is not None else self.poster_url
        self.title = title if title is not None else self.title
        self.url = url if url is not None else self.url
        self.thumbnail = thumbnail if thumbnail is not None else self.thumbnail
        self.posted_at = posted_at if posted_at is not None else self.posted_at
        self.updated_at = updated_at if updated_at is not None else self.updated_at
        self.tags = tags if tags is not None else self.tags
        self.is_deleted = is_deleted if is_deleted is not None else self.is_deleted
        self.description = description if description is not None else self.description
        self.duration = duration if duration is not None else self.duration
        self.view_count = view_count if view_count is not None else self.view_count
        self.like_count = like_count if like_count is not None else self.like_count
        self.comment_count = comment_count if comment_count is not None else self.comment_count


class Live(Content):
    description: str
    duration: int
    view_count: int
    like_count: int
    comment_count: int

    start_at: str
    end_at: str
    status: str
    archive_enabled_at: str

    def __init__(self, id: str) -> None:
        super().__init__(id)
        self.description = None
        self.duration = None
        self.view_count = None
        self.like_count = None
        self.comment_count = None
        self.start_at = None
        self.end_at = None
        self.status = None
        self.archive_enabled_at = None

    def set_value(
        self,
        poster_id: str = None,
        poster_name: str = None,
        poster_url: str = None,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: str = None,
        updated_at: str = None,
        tags: list[str] = None,
        is_deleted: bool = None,
        description: str = None,
        duration: int = None,
        view_count: int = None,
        like_count: int = None,
        comment_count: int = None,
        start_at: str = None,
        end_at: str = None,
        status: str = None,
        archive_enabled_at: str = None,
    ) -> None:
        """属性を設定する

        すべての属性を一度に設定することができる。
        """
        self.poster_id = poster_id
        self.poster_name = poster_name
        self.poster_url = poster_url
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.posted_at = posted_at
        self.updated_at = updated_at
        self.tags = tags
        self.is_deleted = is_deleted
        self.description = description
        self.duration = duration
        self.view_count = view_count
        self.like_count = like_count
        self.comment_count = comment_count
        self.start_at = start_at
        self.end_at = end_at
        self.status = status
        self.archive_enabled_at = archive_enabled_at

    def update_value(
        self,
        poster_id: str = None,
        poster_name: str = None,
        poster_url: str = None,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: str = None,
        updated_at: str = None,
        tags: list[str] = None,
        is_deleted: bool = None,
        description: str = None,
        duration: int = None,
        view_count: int = None,
        like_count: int = None,
        comment_count: int = None,
        start_at: str = None,
        end_at: str = None,
        status: str = None,
        archive_enabled_at: str = None,
    ) -> None:
        """属性を更新する

        すべての属性を一度に更新することができる。
        """
        self.poster_id = poster_id if poster_id is not None else self.poster_id
        self.poster_name = poster_name if poster_name is not None else self.poster_name
        self.poster_url = poster_url if poster_url is not None else self.poster_url
        self.title = title if title is not None else self.title
        self.url = url if url is not None else self.url
        self.thumbnail = thumbnail if thumbnail is not None else self.thumbnail
        self.posted_at = posted_at if posted_at is not None else self.posted_at
        self.updated_at = updated_at if updated_at is not None else self.updated_at
        self.tags = tags if tags is not None else self.tags
        self.is_deleted = is_deleted if is_deleted is not None else self.is_deleted
        self.description = description if description is not None else self.description
        self.duration = duration if duration is not None else self.duration
        self.view_count = view_count if view_count is not None else self.view_count
        self.like_count = like_count if like_count is not None else self.like_count
        self.comment_count = comment_count if comment_count is not None else self.comment_count
        self.start_at = start_at if start_at is not None else self.start_at
        self.end_at = end_at if end_at is not None else self.end_at
        self.status = status if status is not None else self.status
        self.archive_enabled_at = archive_enabled_at if archive_enabled_at is not None else self.archive_enabled_at


class News(Content):
    body: str

    def __init__(self, id: str) -> None:
        super().__init__(id)
        self.body = None

    def set_value(
        self,
        poster_id: str = None,
        poster_name: str = None,
        poster_url: str = None,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: str = None,
        updated_at: str = None,
        tags: list[str] = None,
        is_deleted: bool = None,
        body: str = None,
    ) -> None:
        """属性を設定する

        すべての属性を一度に設定することができる。
        """
        self.poster_id = poster_id
        self.poster_name = poster_name
        self.poster_url = poster_url
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.posted_at = posted_at
        self.updated_at = updated_at
        self.tags = tags
        self.is_deleted = is_deleted
        self.body = body

    def update_value(
        self,
        poster_id: str = None,
        poster_name: str = None,
        poster_url: str = None,
        title: str = None,
        url: str = None,
        thumbnail: str = None,
        posted_at: str = None,
        updated_at: str = None,
        tags: list[str] = None,
        is_deleted: bool = None,
        body: str = None,
    ) -> None:
        """属性を更新する

        すべての属性を一度に更新することができる。
        """
        self.poster_id = poster_id if poster_id is not None else self.poster_id
        self.poster_name = poster_name if poster_name is not None else self.poster_name
        self.poster_url = poster_url if poster_url is not None else self.poster_url
        self.title = title if title is not None else self.title
        self.url = url if url is not None else self.url
        self.thumbnail = thumbnail if thumbnail is not None else self.thumbnail
        self.posted_at = posted_at if posted_at is not None else self.posted_at
        self.updated_at = updated_at if updated_at is not None else self.updated_at
        self.tags = tags if tags is not None else self.tags
        self.is_deleted = is_deleted if is_deleted is not None else self.is_deleted
        self.body = body if body is not None else self.body
