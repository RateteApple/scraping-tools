# coding: UTF-8

from __future__ import annotations
import logging
import json
import feedparser
import os
from datetime import datetime, timedelta

from googleapiclient.discovery import build
import isodate

from my_utilities.debug import execute_time
from .base_class import Platform, Live, Video


logger = logging.getLogger(__name__)

THUMBNAIL_SIZES = ("maxres", "standard", "high", "medium", "default")


@execute_time()
class YTChannel(Platform):
    """YouTubeAPIのヘルパークラス"""

    # APIクライアントを作成
    client = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])

    def __del__(self) -> None:
        # APIクライアントを削除
        del self.client

    def get_ids(self, requet_type: str = "api", limit: int = 5) -> list[dict]:
        """チャンネルのコンテンツのIDを取得するメソッド

        Args:
            requet_type (str, optional): 取得方法. Defaults to "api".
                "api": APIを使用して取得
                "feed": RSSフィードを使用して取得

            limit (int, optional): 取得するコンテンツの数. Defaults to 5.

        Returns:
            list[dict]: コンテンツのIDとetagのリスト
                dict: {"id": str, "etag": str}
        """
        if requet_type == "api":
            contents = self.__get_ids_from_api(limit)
        elif requet_type == "feed":
            contents = self.__get_ids_from_feed()
        else:
            raise ValueError(f"resquet_type must be 'api' or 'feed', not '{requet_type}'")

        return contents

    def __get_ids_from_api(self, limit: int) -> list[dict]:
        """チャンネルのコンテンツを取得するメソッド"""
        # APIで情報を取得
        res = self.client.search().list(channelId=self.id, part="snippet", maxResults=limit, type="video", order="date", safeSearch="none").execute()

        # IDとetagを取得
        contents = []
        for item in res["items"]:
            content = {"id": item["id"]["videoId"], "etag": item["etag"]}
            contents.append(content)

        return contents

    def __get_ids_from_feed(self) -> list[dict]:
        """チャンネルのコンテンツを取得するメソッド

        15件までしか取得できない"""
        # feedを取得
        feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={self.id}")

        # feedが正しく取得できているか確認
        if feed["status"] > 400 or feed["bozo"] != False:
            raise Exception("Failed to get feed")  # FIXME

        # 情報を辞書にまとめる
        contents = []
        for item in feed["entries"]:
            content = {"id": item["yt_videoid"]}
            contents.append(content)

        return contents

    def get_detail(self, ids: list) -> list:
        """コンテンツの詳細を取得するメソッド

        Args:
            ids (list): IDのリスト

        Returns:
            list: コンテンツのリスト
        """
        # APIで情報を取得
        snippet: dict = self.client.videos().list(id=",".join(ids), part="snippet").execute()
        statistics: dict = self.client.videos().list(id=",".join(ids), part="statistics").execute()
        streaming_details: dict = self.client.videos().list(id=",".join(ids), part="liveStreamingDetails").execute()
        content_details: dict = self.client.videos().list(id=",".join(ids), part="contentDetails").execute()

        # # デバッグ用の出力
        # with open("snippet.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(snippet, indent=4, ensure_ascii=False))
        # with open("statistics.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(statistics, indent=4, ensure_ascii=False))
        # with open("streaming_details.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(streaming_details, indent=4, ensure_ascii=False))
        # with open("content_details.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(content_details, indent=4, ensure_ascii=False))

        # 取得したアイテムを結合
        items = []
        for sni, sta, stre, con in zip(snippet["items"], statistics["items"], streaming_details["items"], content_details["items"]):
            item = {**sni, **sta, **stre, **con}
            items.append(item)

        # # デバッグ用の出力
        # with open("items.json", "w", encoding="UTF-8") as f:
        #     f.write(json.dumps(items, indent=4, ensure_ascii=False))

        # 情報を取得
        contents = []
        for item in items:
            content = self.__item_to_instance(item)
            contents.append(content)

        return contents

    def __item_to_instance(self, item: dict) -> Video:
        """アイテムをインスタンスに変換するメソッド"""
        # ID
        id = item["id"]
        # 投稿日時
        posted_at = datetime.fromisoformat(item["snippet"]["publishedAt"])
        # 投稿者ID
        poster_id = item["snippet"]["channelId"]
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
        if "liveStreamingDetails" in item:
            instance = YTLive(id)

            # 放送中
            if item["snippet"]["liveBroadcastContent"] == "live":
                status = "now"
                start_at = datetime.fromisoformat(item["liveStreamingDetails"]["actualStartTime"])
                end_at = None
                duration = None
            # 放送予定
            elif "scheduledStartTime" in item["liveStreamingDetails"]:
                status = "future"
                start_at = datetime.fromisoformat(item["liveStreamingDetails"]["scheduledStartTime"])
                end_at = None
                duration = None
            # 放送済み
            else:
                status = "past"
                start_at = datetime.fromisoformat(item["liveStreamingDetails"]["actualStartTime"])
                end_at = datetime.fromisoformat(item["liveStreamingDetails"]["actualEndTime"])
                duration: timedelta = isodate.parse_duration(item["contentDetails"]["duration"])

            # インスタンスに情報を追加
            instance.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
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
            duration = isodate.parse_duration(item["contentDetails"]["duration"])
            # インスタンスに情報を追加
            instance.set_value(
                poster_id=poster_id,
                poster_name=poster_name,
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


@execute_time()
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


@execute_time()
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
