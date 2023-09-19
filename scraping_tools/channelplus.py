# coding: utf-8

from __future__ import annotations
import logging
from datetime import datetime, timedelta
import time
import re
import os
from pprint import pprint

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException

from .base_class import ScrapingMixin, Platform, Live, Video, News
from .common_func import get_matching_element, get_matching_all_elements, parse_video_duration, scraping_in_new_tab
from my_utilities.debug import execute_time


logger = logging.getLogger(__name__)

root_xpath: str = '//div[@id="root"]'
HEADER_XPATH: str = '//div[@id="root"]/div/div[1]'
main_xpath: str = '//div[@id="root"]/div/div[2]/div[1]'
footer_xpath: str = '//div[@id="root"]/div/div[2]/div[2]'
not_found_xpath: str = '//h5[text()="ページを表示することができませんでした"]'
not_found_xpath2: str = '//h5[text()="お探しのページは見つかりませんでした"]'
LABEL_XPATH: str = '//span[@class="MuiChip-label MuiChip-labelSmall"]'


@execute_time()
class ChannelPlusChannel(Platform, ScrapingMixin):
    """ニコニコチャンネルプラスのコンテンツを取得するクラス"""

    def __init__(self, id: str) -> None:
        """チャンネルプラスではIDが設定できないためURLに含まれている名前を設定"""
        super().__init__(id)

    # 画像なしで読み込むと上手くいかないためオーバーライド
    def open_browser(self) -> None:
        """ブラウザを開く

        環境変数SCRAPING_TOOLS_HEADLESS_MODEがTrueの場合はヘッドレスモードで起動する。
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")  # 保護機能を無効化
        options.add_argument("--disable-gpu")  # GPUの使用を無効化
        options.add_argument("--window-size=1920,1080")  # Windowサイズを1920x1080に設定
        options.add_experimental_option("excludeSwitches", ["enable-logging"])  # ログを無効化
        # options.add_argument("--blink-settings=imagesEnabled=false")  # 画像を読み込まない
        options.add_argument("--disable-extensions")  # 拡張機能を無効化

        # FIXME

        if os.environ.get("SCRAPING_TOOLS_HEADLESS_MODE") == "True":
            options.add_argument("--headless")

        self.driver = webdriver.Chrome(options)

        return self.driver

    # トップページの生放送を取得する
    def get_live(self) -> list[ChannelPlusLive]:
        """ニコニコチャンネルプラスの生放送ページから配信中の放送と放送予定を取得するメソッド"""
        # 生放送ページを開く
        self.driver.get(f"https://nicochannel.jp/{self.id}/lives")

        # セクションを取得出来るまでリトライ
        start = time.time()
        while True:
            sections: list = self.driver.find_elements(By.XPATH, f"{main_xpath}/div/div")
            if len(sections) >= 2:
                break
            if time.time() - start > 20:
                raise Exception("not found sections")  # FIXME

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
        # 状態
        status: str = "future"
        # URL
        url: str = item.get_attribute("href")
        # ID
        id: str = url.split("/")[-1]
        # 投稿者ID
        poster_id: str = url.split("/")[-3]
        # タイトル
        title: str = item.find_element(By.XPATH, "div[2]/div[1]/h6").text
        # サムネイル
        thumbnail: str = item.find_element(By.XPATH, "div").get_attribute("style")
        thumbnail: str = re.search(r"https.*(\d+)", thumbnail).group()
        # 開始予定時刻 ex:'09/16 21:00', '今日 21:00' etc...
        start_at: WebElement = get_matching_element(base=item, tag="span", attribute="class", pattern=r"^.*MuiTypography-caption.*$")
        start_at: str = start_at.text
        try:
            start_at: datetime = datetime.strptime(start_at, "%m/%d %H:%M")
        except:
            time_ = start_at[-5:]  # 後ろの時間部分を取得
            hour, minute = time_.split(":")  # 時間部分を取得
            if "今日" in start_at:
                now: datetime = datetime.now()
                start_at: datetime = now.replace(hour=int(hour), minute=int(minute))
            elif "明日" in start_at:
                tommorow: datetime = datetime.now() + timedelta(days=1)
                start_at: datetime = tommorow.replace(hour=int(hour), minute=int(minute))
            else:
                raise Exception("invalid start_at")  # FIXME
        # 年を設定
        now: datetime = datetime.now()
        if start_at.month < now.month:
            start_at: datetime = start_at.replace(year=now.year + 1)
        else:
            start_at: datetime = start_at.replace(year=now.year)

        # インスタンスを作成
        live = ChannelPlusLive(poster_id, id)
        live.set_value(
            poster_id=poster_id,
            title=title,
            url=url,
            thumbnail=thumbnail,
            start_at=start_at,
            status=status,
        )

        return live

    # トップページの動画を取得する
    def get_video(self, type_: str = "upload") -> list[ChannelPlusVideo]:
        """ニコニコチャンネルプラスの動画ページをスクレイピングする"""
        # 動画ページを開く
        self.driver.get(f"https://nicochannel.jp/{self.id}/videos")

        # 指定されたタイプのボタンをクリックして遷移
        if type_ == "upload":
            uploaded_btn = WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//span[text()="アップロード動画"]/..')))
            uploaded_btn.click()
        elif type_ == "archive":
            archive_btn = WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//span[text()="アーカイブ動画"]/..')))
            archive_btn.click()
        elif type_ == "all":
            pass
        else:
            raise ValueError("type must be 'upload' or 'archive' or 'all'")

        # 一番下にたどり着くまでスクロール
        while True:
            # 一番下までスクロール
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # 「すべて表示しています」というテキストがあるか確認
            try:
                self.driver.find_element(By.XPATH, '//span[text()="すべて表示しています"]')
            except NoSuchElementException:
                continue
            else:
                break

        # アイテムを取得
        main: WebElement = self.driver.find_element(By.XPATH, '//div[@id="root"]/div/div[2]/div[1]')
        items: list = get_matching_all_elements(base=main, tag="div", attribute="class", pattern=r"^.*MuiGrid-item.*$")
        if not items:
            return []

        # 各アイテムから動画情報を取得
        videos = [self.__video_item(item) for item in items]

        return videos

    def __video_item(self, item: WebElement) -> ChannelPlusVideo:
        item_upper: WebElement = item.find_element(By.XPATH, "./div/div/div[1]")  # //*[@id="app-layout"]/div[2]/div[1]/div/div[3]/div/div/div/div/div/div/div[1]
        item_under: WebElement = item.find_element(By.XPATH, "./div/div/div[2]")  # //*[@id="app-layout"]/div[2]/div[1]/div/div[3]/div/div/div/div/div/div/div[2]
        # URL
        url: str = item_under.find_element(By.XPATH, ".//a").get_attribute("href")
        # 投稿者ID
        poster_id: str = url.split("/")[-3]
        # ID
        id: str = url.split("/")[-1]
        # タイトル
        title: str = item_under.find_element(By.XPATH, ".//h6").text
        # サムネイル
        thumbnail: str = item_upper.find_element(By.XPATH, ".//img").get_attribute("src")
        # 投稿日時
        posted_at: str = item_under.find_element(By.XPATH, ".//span").text  # ex:"2023/07/06", "〇日前"
        try:
            posted_at: datetime = datetime.strptime(posted_at, "%Y/%m/%d")
        except:
            if "日前" in posted_at:
                before_days: int = int(posted_at[0])
                posted_at: datetime = datetime.now() - timedelta(days=before_days)
            elif "時間前" in posted_at:
                before_hours: int = int(posted_at[0])
                posted_at: datetime = datetime.now() - timedelta(hours=before_hours)
            else:
                raise Exception("invalid posted_at")  # FIXME
        # 動画時間
        on_iamge: list = item_upper.find_elements(By.XPATH, ".//div")  # 1つめにラベル、2つめに時間が入っている
        duration: str = on_iamge[-1].text  # ex:"00:00:00", "00:00"
        duration: timedelta = parse_video_duration(duration)
        # 再生数
        view_count: WebElement = item_under.find_element(By.XPATH, "./div/div/div[1]/div")
        view_count: int = int(view_count.text)
        # コメント数
        comment_count: WebElement = item_under.find_element(By.XPATH, "./div/div/div[2]/div")
        comment_count: int = int(comment_count.text)

        # インスタンスを作成
        video = ChannelPlusVideo(poster_id, id)
        video.set_value(
            poster_id=poster_id,
            title=title,
            url=url,
            thumbnail=thumbnail,
            posted_at=posted_at,
            duration=duration,
            view_count=view_count,
            comment_count=comment_count,
        )

        return video

    # トップページのニュースを取得する
    def get_news(self, limit: int = 3) -> list[ChannelPlusNews]:
        # ニュースページを開く
        self.driver.get(f"https://nicochannel.jp/{self.id}/articles/news")

        # 一番下にたどり着くまでスクロール
        while True:
            # 一番下までスクロール
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # 「すべて表示しています」というテキストがあるか確認
            try:
                self.driver.find_element(By.XPATH, '//span[text()="すべて表示しています"]')
            except NoSuchElementException:
                continue
            else:
                break

        # 上に戻る
        self.driver.execute_script("window.scrollTo(0, 0);")

        # メインの要素を取得
        main = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, main_xpath)))

        # アイテムを取得
        items = get_matching_all_elements(base=main, tag="div", attribute="class", pattern=r"^.*MuiPaper-rounded.*$", limit=limit)
        if not items:
            return []

        # 各ニュースから情報を取得
        newses = []
        for item in items:
            newses.append(self.__news_item(item))
            time.sleep(1)  # FIXME

        # 結果を返す
        return newses

    def __news_item(self, item: WebElement) -> ChannelPlusNews:
        # タイトル
        title: str = item.find_element(By.XPATH, ".//h6").text
        # サムネイル
        thumbnail: str = item.find_element(By.XPATH, ".//img").get_attribute("src")

        # 新しいタブを開く
        current_tab = self.driver.current_window_handle
        self.driver.switch_to.new_window("tab")
        # 新しいタブに遷移するまで待機
        while current_tab != self.driver.current_window_handle:
            break

        # 情報を取得
        news = self.__news_page_in_new_tab(title)

        # タブを閉じて元のタブに戻る
        self.driver.close()
        self.driver.switch_to.window(current_tab)

        # サムネイル情報を追加
        news.update_value(thumbnail=thumbnail)

        return news

    def __news_page_in_new_tab(self, title: str) -> ChannelPlusNews:
        # ページを開く
        self.driver.get(f"https://nicochannel.jp/{self.id}/articles/news")

        # 対象のニュースをクリック
        target_news = WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH, f'//h6[text()="{title}"]')))
        target_news.click()

        # ID
        id = self.driver.current_url.split("/")[-1]
        # 投稿者ID
        poster_id = self.id
        # タイトル
        title: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//meta[@property="og:title"]')))
        title: str = title.get_attribute("content")
        # URL
        url: str = self.driver.current_url
        # 投稿日時
        posted_at: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f"{main_xpath}/div/div[4]/span")))
        posted_at: str = posted_at.text  # ex:"2023/07/06","〇日前","〇時間前"
        try:
            posted_at: datetime = datetime.strptime(posted_at, "%Y/%m/%d")
        except:
            if "日前" in posted_at:
                before_days: int = int(posted_at[0])
                posted_at: datetime = datetime.now() - timedelta(days=before_days)
            elif "時間前" in posted_at:
                before_hours: int = int(posted_at[0])
                posted_at: datetime = datetime.now() - timedelta(hours=before_hours)
            else:
                raise Exception("invalid posted_at")  # FIXME
        # 内容
        body: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f"{main_xpath}/div/div[5]")))
        body: str = body.text

        # インスタンスを作成
        news = ChannelPlusNews(poster_id, id)
        news.set_value(
            poster_id=poster_id,
            title=title,
            url=url,
            posted_at=posted_at,
            body=body,
        )

        return news


class ChannelPlusContentMixin(ScrapingMixin):
    """ニコニコチャンネルプラスのコンテンツページをスクレイピングするメソッドをまとめたクラス"""

    # TODO: ニコニコチャンネルプラスのコンテンツページをスクレイピングする
    def __content_page(self) -> dict:
        """ニコニコチャンネルプラスのコンテンツページをスクレイピングする"""
        # コンテンツのページを開く
        self.driver.get(f"https://nicochannel.jp/{self.poster_id}/live/{self.id}")

        # メインの要素を取得
        main: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, main_xpath)))

        # タイトル
        title: str = main.find_element(By.XPATH, '//meta[@property="og:title"]').get_attribute("content")
        # URL
        url: str = self.driver.current_url
        # ID
        id: str = url.split("/")[-1]
        # 投稿者ID
        poster_id: str = url.split("/")[-3]
        # サムネイル
        thumbnail: str = main.find_element(By.XPATH, '//meta[@property="og:image"]').get_attribute("content")
        # 説明文
        description: str = main.find_element(By.XPATH, '//meta[@name="description"]').get_attribute("content")

        # ラベルからコンテンツの種類と状態を取得
        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//div[@id="video-page-wrapper"]')))
        labels: list = main.find_elements(By.XPATH, LABEL_XPATH)
        for label in labels:
            # COMING SOON
            if label.text == "COMING SOON":
                status: str = "future"
            # STREAMING
            elif label.text == "STREAMING":
                status: str = "now"
            else:
                status = None
            # 会員限定
            if label.text == "会員限定":
                pass
            # 一部無料
            if label.text == "一部無料":
                pass

        return result


class ChannelPlusVideo(Video, ChannelPlusContentMixin):
    """ニコニコチャンネルプラスの動画情報を格納するクラス"""

    def __init__(self, poster_id: str, id: str) -> None:
        super().__init__(id)
        self.poster_id = poster_id


class ChannelPlusLive(Live, ChannelPlusContentMixin):
    """ニコニコチャンネルプラスの生放送情報を格納するクラス"""

    def __init__(self, poster_id: str, id: str) -> None:
        super().__init__(id)
        self.poster_id = poster_id


class ChannelPlusNews(News):
    """ニコニコチャンネルプラスのニュース情報を格納するクラス"""

    def __init__(self, poster_id: str, id: str) -> None:
        super().__init__(id)
        self.poster_id = poster_id
