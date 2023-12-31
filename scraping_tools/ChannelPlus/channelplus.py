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

from ..common.base_class import ScrapingMixin, Platform, Live, Video, News
from ..common.common_func import get_matching_element, get_matching_all_elements, parse_video_duration
from my_utilities.debug import execute_time


logger = logging.getLogger(__name__)

ROOT_XPATH: str = '//div[@id="root"]'
HEADER_XPATH: str = '//div[@id="root"]/div/div[1]'
MAIN_XPATH: str = '//div[@id="root"]/div/div[2]/div[1]'
FOOTER_XPATH: str = '//div[@id="root"]/div/div[2]/div[2]'
NOT_FOUND_XPATH: str = '//h5[text()="ページを表示することができませんでした"]'
NOT_FOUND_XPATH2: str = '//h5[text()="お探しのページは見つかりませんでした"]'
LABEL_XPATH: str = '//span[@class="MuiChip-label MuiChip-labelSmall"]'

# FIXME: 画像を読み込むまで待機する処理が必要


class ChannelPlusChannel(Platform, ScrapingMixin):
    """ニコニコチャンネルプラスのコンテンツを取得するクラス"""

    _img_load = True

    def __init__(self, id: str) -> None:
        """IDの代わりに名前を設定"""
        super().__init__(id)

    # トップページの生放送を取得する
    def get_live(self) -> list[ChannelPlusLive]:
        logger.info(f"Scraping for NicoNicoChannelPlus's live page...")
        lives = self.__live_page()
        logger.info(f"Success scraping for NicoNicoChannelPlus's live page")

        return lives

    def __live_page(self) -> list[ChannelPlusLive]:
        """ニコニコチャンネルプラスの生放送ページから配信中の放送と放送予定を取得するメソッド"""

        def get_from_now_section(now_section: WebElement) -> list[ChannelPlusLive]:
            """配信中の生放送情報を取得する"""
            # item Xpath "//*[@id="app-layout"]/div[2]/div[1]/div/div[1]/div/div/a"
            items = get_matching_all_elements(base=now_section, tag="a", attribute="class", pattern=r"^MuiButtonBase-root MuiCardActionArea-root.*$")
            if not items:
                return []

            # 各アイテムから情報を取得
            lives = [now_item(item) for item in items]

            return lives

        def now_item(item: WebElement) -> ChannelPlusLive:
            # 状態
            status: str = "now"
            # URL
            url: str = item.get_attribute("href")
            # ID
            id: str = url.split("/")[-1]
            # タイトル
            title: str = item.find_element(By.XPATH, ".//h6").text
            # サムネイル
            thumbnail: str = item.find_element(By.XPATH, "div[1]").get_attribute("style")
            thumbnail: str = re.search(r"https.*(\d+)", thumbnail).group()

            # インスタンスを作成
            live = ChannelPlusLive(poster_id, id)
            live.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                poster_url=poster_url,
                title=title,
                url=url,
                thumbnail=thumbnail,
                status=status,
            )

            return live

        def get_from_future_section(future_section: WebElement) -> list[ChannelPlusLive]:
            """放送予定の生放送情報を取得する"""
            # アイテムの取得  //*[@id="app-layout"]/div[2]/div[1]/div[1]/div/div/div/div/a
            items = get_matching_all_elements(base=future_section, tag="a", attribute="class", pattern=r"^MuiButtonBase-root MuiCardActionArea-root.*$")
            if not items:
                return []

            # 各アイテムから情報を取得
            lives = [future_item(item) for item in items]

            return lives

        def future_item(item: WebElement) -> ChannelPlusLive:
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
            start_at: str = self.__convert_future_item_start_at(start_at)

            # インスタンスを作成
            live = ChannelPlusLive(poster_id, id)
            live.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                poster_url=poster_url,
                title=title,
                url=url,
                thumbnail=thumbnail,
                start_at=start_at,
                status=status,
            )

            return live

        # 生放送ページを開く
        self._driver.get(f"https://nicochannel.jp/{self.id}/lives")

        # 投稿者ID
        poster_id: str = self._driver.current_url.split("/")[-2]
        # 投稿者URL
        poster_url: str = f"https://nicochannel.jp/{poster_id}"
        # 投稿者名
        poster_name: str = self.get_poster_name()

        # セクションを取得出来るまでリトライ
        start = time.time()
        while True:
            sections: list = self._driver.find_elements(By.XPATH, f"{MAIN_XPATH}/div/div")
            if len(sections) >= 2:
                break
            if time.time() - start > self._timeout:
                raise Exception("not found sections")  # FIXME

        # 生放送のリストを取得
        lives = []
        if len(sections) == 3:
            lives.extend(get_from_now_section(sections[0]))
            lives.extend(get_from_future_section(sections[1]))
        else:
            lives.extend(get_from_future_section(sections[0]))

        # 結果を返す
        return lives

    # 予定開始時刻をISO8601形式に変換する(放送予定限定)
    def __convert_future_item_start_at(self, start_at: str) -> str:
        """放送予定の生放送情報の開始予定時刻をISO8601形式に変換する"""
        # start:str ex:'09/16 21:00', '今日 21:00' etc...
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
        start_at: str = start_at.isoformat()

        return start_at

    # トップページの動画を取得する
    def get_video(self, type_: str = "upload", limit: int = 5) -> list[ChannelPlusVideo]:
        logger.info(f"Scraping for NicoNicoChannelPlus's video page...")
        videos = self.__video_page(type_, limit)
        logger.info(f"Success scraping for NicoNicoChannelPlus's video page")

        return videos

    def __video_page(self, type_: str, limit: int) -> list[ChannelPlusVideo]:
        """ニコニコチャンネルプラスの動画ページをスクレイピングする"""

        def video_item(item: WebElement) -> ChannelPlusVideo:
            item_upper: WebElement = item.find_element(By.XPATH, "./div/div/div[1]")  # //*[@id="app-layout"]/div[2]/div[1]/div/div[3]/div/div/div/div/div/div/div[1]
            item_under: WebElement = item.find_element(By.XPATH, "./div/div/div[2]")  # //*[@id="app-layout"]/div[2]/div[1]/div/div[3]/div/div/div/div/div/div/div[2]
            # URL
            url: str = item_under.find_element(By.XPATH, ".//a").get_attribute("href")
            # ID
            id: str = url.split("/")[-1]
            # タイトル
            title: str = item_under.find_element(By.XPATH, ".//h6").text
            # サムネイル
            thumbnail: str = item_upper.find_element(By.XPATH, ".//img").get_attribute("src")
            # 投稿日時
            posted_at: str = item_under.find_element(By.XPATH, ".//span").text  # ex:"2023/07/06", "〇日前"
            posted_at: str = self.__convert_posted_at(posted_at)
            # 動画時間
            on_iamge: list = item_upper.find_elements(By.XPATH, ".//div")  # 1つめにラベル、2つめに時間が入っている
            duration: str = on_iamge[-1].text  # ex:"00:00:00", "00:00"
            duration: timedelta = parse_video_duration(duration)
            duration: int = int(duration.total_seconds())
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
                poster_name=poster_name,
                poster_url=poster_url,
                title=title,
                url=url,
                thumbnail=thumbnail,
                posted_at=posted_at,
                duration=duration,
                view_count=view_count,
                comment_count=comment_count,
            )

            return video

        # 動画ページを開く
        self._driver.get(f"https://nicochannel.jp/{self.id}/videos")

        # 指定されたタイプのボタンをクリックして遷移
        if type_ == "upload":
            uploaded_btn = WebDriverWait(self._driver, self._timeout).until(EC.element_to_be_clickable((By.XPATH, '//span[text()="アップロード動画"]/..')))
            uploaded_btn.click()
        elif type_ == "archive":
            archive_btn = WebDriverWait(self._driver, self._timeout).until(EC.element_to_be_clickable((By.XPATH, '//span[text()="アーカイブ動画"]/..')))
            archive_btn.click()
        elif type_ == "all":
            pass
        else:
            raise ValueError("type must be 'upload' or 'archive' or 'all'")

        while True:  # FIXME:limitが増えた際にスクロール処理が上手くいくか不明
            # 表示されているアイテム数を取得
            main: WebElement = self._driver.find_element(By.XPATH, MAIN_XPATH)
            items: list = get_matching_all_elements(base=main, tag="div", attribute="class", pattern=r"^.*MuiGrid-item.*$")
            # アイテムがなければ空リストを返して終了
            if not items:
                return []
            # アイテム数が指定数以上になったら終了
            if len(items) >= limit:
                break

            # 最後のアイテムの位置にスクロール
            self._driver.execute_script("arguments[0].scrollIntoView();", items[-1])

            # 「すべて表示しています」というテキストがあるか確認
            try:
                self._driver.find_element(By.XPATH, '//span[text()="すべて表示しています"]')
            except NoSuchElementException:
                continue
            else:
                break

        # 投稿者名
        poster_name: str = self.get_poster_name()
        # 投稿者URL
        poster_url: str = f"https://nicochannel.jp/{self.id}"
        # 投稿者ID
        poster_id: str = self._driver.current_url.split("/")[-2]

        # 各アイテムから動画情報を取得
        videos = [video_item(item) for item in items]

        return videos

    # トップページのニュースを取得する
    def get_news(self, limit: int = 1) -> list[ChannelPlusNews]:
        logger.info(f"Scraping for NicoNicoChannelPlus's news page...")
        newses = self.__news_page(limit)
        logger.info(f"Success scraping for NicoNicoChannelPlus's news page")

        return newses

    def __news_page(self, limit: int) -> list[ChannelPlusNews]:
        """ニコニコチャンネルプラスのニュースページをスクレイピングする"""

        def news_item(item: WebElement) -> ChannelPlusNews:
            # タイトル
            title: str = item.find_element(By.XPATH, ".//h6").text
            # サムネイル
            while True:
                try:
                    thumbnail: str = item.find_element(By.XPATH, ".//img").get_attribute("src")
                    break
                except:
                    pass

            # 新しいタブを開く
            current_tab = self._driver.current_window_handle
            self._driver.switch_to.new_window("tab")
            # 新しいタブに遷移するまで待機
            while current_tab != self._driver.current_window_handle:
                break

            # ニュースの個別ページに遷移してインスタンスを作成
            news: ChannelPlusNews = news_page_in_new_tab(title)

            # タブを閉じて元のタブに戻る
            self._driver.close()
            self._driver.switch_to.window(current_tab)

            # サムネイル情報を追加
            news.update_value(thumbnail=thumbnail)

            return news

        def news_page_in_new_tab(title: str) -> ChannelPlusNews:
            # ページを開く
            self._driver.get(f"https://nicochannel.jp/{self.id}/articles/news")

            # 対象のニュースをクリック
            target_news = WebDriverWait(self._driver, self._timeout).until(EC.element_to_be_clickable((By.XPATH, f'//h6[text()="{title}"]')))
            target_news.click()

            # ID
            id = self._driver.current_url.split("/")[-1]
            # タイトル
            title: WebElement = WebDriverWait(self._driver, self._timeout).until(EC.presence_of_element_located((By.XPATH, '//meta[@property="og:title"]')))
            title: str = title.get_attribute("content")
            # URL
            url: str = self._driver.current_url
            # 投稿日時
            posted_at: WebElement = WebDriverWait(self._driver, self._timeout).until(EC.presence_of_element_located((By.XPATH, f"{MAIN_XPATH}/div/div[4]/span")))
            posted_at: str = posted_at.text  # ex:"2023/07/06","〇日前","〇時間前"
            posted_at: str = self.__convert_posted_at(posted_at)
            # 内容
            body: WebElement = WebDriverWait(self._driver, self._timeout).until(EC.presence_of_element_located((By.XPATH, f"{MAIN_XPATH}/div/div[5]")))
            body: str = body.text

            # インスタンスを作成
            news = ChannelPlusNews(poster_id, id)
            news.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                poster_url=poster_url,
                title=title,
                url=url,
                posted_at=posted_at,
                body=body,
            )

            return news

        # ニュースページを開く
        self._driver.get(f"https://nicochannel.jp/{self.id}/articles/news")

        # 要素を読み込むためスクロール
        while True:
            # 表示されているアイテム数を取得
            main: WebElement = self._wait.until(EC.presence_of_element_located((By.XPATH, MAIN_XPATH)))
            items: list = get_matching_all_elements(base=main, tag="div", attribute="class", pattern=r"^.*MuiPaper-rounded.*$")
            # アイテムがなければ空リストを返して終了
            if not items:
                return []
            # アイテム数が指定数以上になったら終了
            if len(items) >= limit:
                break

            # 最後のアイテムの位置にスクロール
            self._driver.execute_script("arguments[0].scrollIntoView();", items[-1])

            # 「すべて表示しています」というテキストがあるか確認
            try:
                self._driver.find_element(By.XPATH, '//span[text()="すべて表示しています"]')
            except NoSuchElementException:
                continue
            else:
                break

        # アイテム数を制限
        items = items[:limit]

        # 投稿者名
        poster_name: str = self.get_poster_name()
        # 投稿者ID
        poster_id: str = self._driver.current_url.split("/")[-3]
        # 投稿者URL
        poster_url: str = f"https://nicochannel.jp/{poster_id}"

        # 各ニュースから情報を取得
        newses = []
        for item in items:
            # 2秒毎にページを開くように調整
            start = time.time()
            newses.append(news_item(item))
            end = time.time()
            execute_time = end - start
            if execute_time < 2:
                time.sleep(2 - execute_time)

        # 結果を返す
        return newses

    # 投稿日時をISO8601形式に変換する(動画、ニュース共通)
    def __convert_posted_at(self, posted_at: str) -> str:
        """動画の投稿日時をISO8601形式に変換する"""
        # posted_at:str ex:"2023/07/06", "〇日前", "〇時間前"
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
                raise Exception("invalid posted_at")
        posted_at: str = posted_at.isoformat()

        return posted_at

    # 投稿者名を取得する
    def get_poster_name(self) -> str:
        """投稿者名を取得する"""
        # フッターを取得
        footer: WebElement = WebDriverWait(self._driver, self._timeout).until(EC.presence_of_element_located((By.XPATH, FOOTER_XPATH)))
        poster_name: str = footer.find_element(By.XPATH, ".//h6").text

        return poster_name


class ChannelPlusContentMixin(ScrapingMixin):
    """ニコニコチャンネルプラスのコンテンツページをスクレイピングするメソッドをまとめたクラス"""

    # TODO: ニコニコチャンネルプラスのコンテンツページをスクレイピングする
    def __content_page(self) -> dict:
        """ニコニコチャンネルプラスのコンテンツページをスクレイピングする"""
        pass
        # # コンテンツのページを開く
        # self.driver.get(f"https://nicochannel.jp/{self.poster_id}/live/{self.id}")

        # # メインの要素を取得
        # main: WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, MAIN_XPATH)))

        # # タイトル
        # title: str = main.find_element(By.XPATH, '//meta[@property="og:title"]').get_attribute("content")
        # # URL
        # url: str = self.driver.current_url
        # # ID
        # id: str = url.split("/")[-1]
        # # 投稿者ID
        # poster_id: str = url.split("/")[-3]
        # # サムネイル
        # thumbnail: str = main.find_element(By.XPATH, '//meta[@property="og:image"]').get_attribute("content")
        # # 説明文
        # description: str = main.find_element(By.XPATH, '//meta[@name="description"]').get_attribute("content")

        # # ラベルからコンテンツの種類と状態を取得
        # WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//div[@id="video-page-wrapper"]')))
        # labels: list = main.find_elements(By.XPATH, LABEL_XPATH)
        # for label in labels:
        #     # COMING SOON
        #     if label.text == "COMING SOON":
        #         status: str = "future"
        #     # STREAMING
        #     elif label.text == "STREAMING":
        #         status: str = "now"
        #     else:
        #         status = None
        #     # 会員限定
        #     if label.text == "会員限定":
        #         pass
        #     # 一部無料
        #     if label.text == "一部無料":
        #         pass

        # return result


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
