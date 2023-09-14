# coding: utf-8

from __future__ import annotations
from datetime import datetime, timedelta
import re

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


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
