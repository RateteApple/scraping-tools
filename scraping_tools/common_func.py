import time
from datetime import datetime, timedelta
import re
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


# 正規表現に一致する要素を1つ取得する
def get_matching_element(base: WebElement, tag: str, attribute: str, pattern: str, timeout: int = 10) -> WebElement:
    """正規表現に一致する要素を取得する

    一致する要素がない場合はNoneを返す
    """
    element: WebElement

    # 実行開始時刻を取得
    start = time.time()
    while True:
        # 要素を全て取得
        try:
            elements: list = base.find_elements(By.XPATH, f".//{tag}")
        except StaleElementReferenceException:
            continue

        # 全ての要素を確認
        for element in elements:
            # 指定された属性の値を取得
            try:
                value: str = element.get_attribute(attribute)
            # 要素が見つからない場合は次の要素へ
            except StaleElementReferenceException:
                continue
            # 正規表現に一致したらWebElementを返す
            if re.match(pattern, value):
                return element

        # 実行時間が指定時間を超えたらNoneを返す
        if time.time() - start > timeout:
            return None


# 正規表現に一致する要素を全て取得する
def get_matching_all_elements(base: WebElement, tag: str, attribute: str, pattern: str, timeout: int = 10) -> list:
    """正規表現に一致する要素を全て取得する

    一致する要素が見つからなかった場合は空のリストを返す
    """
    element: WebElement
    match_elements = []

    # 実行開始時刻を取得
    start = time.time()
    while True:
        # 要素を全て取得
        try:
            elements: list = base.find_elements(By.XPATH, f".//{tag}")
        except StaleElementReferenceException:
            continue

        # 全ての要素を確認
        for element in elements:
            # 指定された属性の値を取得
            try:
                value: str = element.get_attribute(attribute)
            # 要素が見つからない場合は次の要素へ
            except StaleElementReferenceException:
                continue
            # 正規表現に一致したらリストに追加
            if re.match(pattern, value):
                match_elements.append(element)

        # 実行時間が指定時間を超えたらリストを返す
        if time.time() - start > timeout:
            return match_elements


# 時間文字列をtimedeltaオブジェクトに変換する
def parse_video_duration(duration_str: str) -> timedelta:
    """時間文字列をtimedeltaオブジェクトに変換する

    例: 1:23:45 -> timedelta(hours=1, minutes=23, seconds=45)
    """
    # 時間、分、秒に分割
    parts: list = duration_str.split(":")
    # 時間、分、秒を取得
    if len(parts) == 3:
        seconds: int = int(parts[-1])
        minutes: int = int(parts[-2])
        hours: int = int(parts[-3])
    elif len(parts) == 2:
        seconds: int = int(parts[-1])
        minutes: int = int(parts[-2])
        hours: int = 0
    # 時間、分、秒に分割できなかった場合はエラー
    else:
        raise ValueError(f"invalid duration_str (duration_str:{duration_str})")

    # timedelta オブジェクトを作成
    video_duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)

    return video_duration
