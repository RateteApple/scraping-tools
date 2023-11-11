# coding: UTF-8

from __future__ import annotations
import logging
import json
import feedparser
import os
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup, Tag

from googleapiclient.discovery import build
import googleapiclient.discovery
import isodate

from ..common.base_class import Platform, Live, Video


logger = logging.getLogger(__name__)

THUMBNAIL_SIZES = ("maxres", "standard", "high", "medium", "default")


class YTChannel:
    """YouTubeAPIのヘルパークラス"""

    # APIクライアントを作成
    client: googleapiclient.discovery.Resource = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])

    def __init__(self, id: str) -> None:
        if "@" in id:
            id = self.search_channel_id(id)
        self.id = id

    def get_from_api(self, limit: int = 5, order: str = "date") -> list[str]:
        """チャンネルのコンテンツを取得するメソッド

        Args:
            limit (int, optional): 取得するコンテンツの数. Defaults to 5.

        Returns:
            list[dict]: コンテンツのIDとetagのリスト
        """
        # APIで情報を取得
        logger.info(f"Channel API requesting...")
        res = self.client.search().list(channelId=self.id, part="snippet", maxResults=limit, type="video", order=order, safeSearch="none").execute()
        logger.info(f"Success to get Channel API response")

        # IDを取得
        ids = [item["id"]["videoId"] for item in res["items"]]

        return ids

    def get_ids_from_feed(self) -> list[str]:
        """チャンネルのコンテンツを取得するメソッド

        15件までしか取得できない"""
        # feedを取得
        feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={self.id}")

        # feedが正しく取得できているか確認
        if feed["status"] > 400 or feed["bozo"] != False:
            raise Exception("Failed to get feed")  # FIXME

        # IDのリストを作成
        ids = [item["yt_videoid"] for item in feed["entries"]]

        return ids

    def get_detail(self, ids: list) -> list:
        """コンテンツの詳細を取得するメソッド

        Args:
            ids (list): IDのリスト

        Returns:
            list: コンテンツのリスト
        """
        if not ids:
            raise ValueError("ids is empty")
        if type(ids) != list:
            raise TypeError("ids is not list")

        # APIで情報を取得
        logger.info(f"Video API requesting...")
        snippet: dict = self.client.videos().list(id=",".join(ids), part="snippet").execute()
        statistics: dict = self.client.videos().list(id=",".join(ids), part="statistics").execute()
        streaming_details: dict = self.client.videos().list(id=",".join(ids), part="liveStreamingDetails").execute()
        content_details: dict = self.client.videos().list(id=",".join(ids), part="contentDetails").execute()
        logger.info(f"Success to get Video API response")

        # # デバッグ用の出力
        # with open("snippet.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(snippet, indent=4, ensure_ascii=False))
        # with open("statistics.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(statistics, indent=4, ensure_ascii=False))
        # with open("streaming_details.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(streaming_details, indent=4, ensure_ascii=False))
        # with open("content_details.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(content_details, indent=4, ensure_ascii=False))

        # レスポンスのアイテムを結合
        items = []
        for sni, sta, stre, con in zip(snippet["items"], statistics["items"], streaming_details["items"], content_details["items"]):
            item = {**sni, **sta, **stre, **con}
            items.append(item)

        # # デバッグ用の出力
        # with open("items.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(items, indent=4, ensure_ascii=False))

        # アイテムからインスタンスを作成してリストに追加
        contents = [self.__item_to_instance(item) for item in items]

        return contents

    def __item_to_instance(self, item: dict) -> Video:
        """アイテムをインスタンスに変換するメソッド"""
        # ID
        id = item["id"]
        # 投稿日時
        posted_at = datetime.fromisoformat(item["snippet"]["publishedAt"])
        posted_at: str = posted_at.isoformat()
        # 投稿者ID
        poster_id = item["snippet"]["channelId"]
        # 投稿者URL
        poster_url = f"https://www.youtube.com/channel/{poster_id}"
        # タイトル
        title = item["snippet"]["title"]
        # 説明文
        description = item["snippet"]["description"]
        # サムネイル
        for size in THUMBNAIL_SIZES:
            if size in item["snippet"]["thumbnails"]:
                thumbnail = item["snippet"]["thumbnails"][size]["url"]
                break
        # 投稿者名
        poster_name = item["snippet"]["channelTitle"]
        # タグ
        tags = item["snippet"]["tags"] if "tags" in item["snippet"] else []
        # 視聴回数
        view_count: int = int(item["statistics"]["viewCount"])
        # 高評価数
        like_count: int = int(item["statistics"]["likeCount"])
        # コメント数
        comment_count: int = int(item["statistics"]["commentCount"])
        # URL
        url = f"https://www.youtube.com/watch?v={id}"

        # 生放送
        # 生放送 "liveStreamingDetails"が存在する場合
        if "liveStreamingDetails" in item:
            instance = YTLive(id)

            # 配信中 "liveBroadcastContent"の値が"live"の場合
            if item["snippet"]["liveBroadcastContent"] == "live":
                status = "now"
                start_at = item["liveStreamingDetails"]["actualStartTime"]
                end_at = None
                duration = None
            # 放送済み "acutalEndTime"が存在する場合
            elif "actualEndTime" in item["liveStreamingDetails"]:
                status = "past"
                start_at = item["liveStreamingDetails"]["actualStartTime"]
                end_at = item["liveStreamingDetails"]["actualEndTime"]
                duration: timedelta = isodate.parse_duration(item["contentDetails"]["duration"])
                duration: int = int(duration.total_seconds())
            # 放送予定 上記のどちらにも当てはまらない場合
            else:
                status = "future"
                start_at = item["liveStreamingDetails"]["scheduledStartTime"]
                end_at = None
                duration = None

            # インスタンスに情報を追加
            instance.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                poster_url=poster_url,
                title=title,
                url=url,
                thumbnail=thumbnail,
                posted_at=posted_at,
                tags=tags,
                is_deleted=False,  # FIXME
                description=description,
                duration=duration,
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                start_at=start_at,
                end_at=end_at,
                status=status,
            )

        # 動画
        else:
            instance = YTVideo(id)
            duration: timedelta = isodate.parse_duration(item["contentDetails"]["duration"])
            duration: int = int(duration.total_seconds())
            # インスタンスに情報を追加
            instance.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
                poster_url=poster_url,
                title=title,
                url=url,
                thumbnail=thumbnail,
                posted_at=posted_at,
                tags=tags,
                is_deleted=False,  # FIXME
                description=description,
                duration=duration,
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
            )

        # インスタンスを返す
        return instance

    # ハンドルからチャンネルIDを取得
    @staticmethod
    def search_channel_id(handle: str) -> str:
        """ハンドルからチャンネルIDを取得するメソッド

        Args:
            handle (str): ハンドル

        Returns:
            str: チャンネルID
        """
        # URLを作成
        url = f"https://www.youtube.com/{handle}"

        # HTTPリクエストで情報を取得
        logger.info(f"Requesting {url}...")
        res = requests.get(url)
        if res.status_code >= 400:
            raise Exception(f"Failed to get {url}")
        else:
            logger.info(f"Success to get {url}")

        # soupを作成
        soup = BeautifulSoup(res.text, "html.parser")
        # itemprop="url"のlinkを取得
        link: Tag = soup.find("link", itemprop="url")
        # linkからchannel_idを取得
        channel_id = link["href"].split("/")[-1]

        return channel_id


class YTVideo(Video):
    def __init__(self, id: str) -> None:
        super().__init__(id)

    def get_detail(self) -> None:
        # TODO
        pass

    @classmethod
    def from_id(self, id: str) -> None:
        # TODO
        pass


class YTLive(Live):
    def __init__(self, id: str) -> None:
        super().__init__(id)

    def get_detail(self) -> None:
        # TODO
        pass

    @classmethod
    def from_id(self, id: str) -> None:
        # TODO
        pass
