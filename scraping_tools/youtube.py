# coding: UTF-8

from __future__ import annotations
import logging
import json

from googleapiclient.discovery import build

from my_utilities.debug_decorator import apply_output_debug


logger = logging.getLogger(__name__)


@apply_output_debug(logger, exclude=["_get_common_part", "_get_live_part"])
class YouTube:
    """YouTubeAPIのヘルパークラス"""

    thumbnail_sizes: list = ["maxres", "standard", "high", "medium", "default"]
    output_api_data: bool = False

    # コンストラクタ
    def __init__(self, API_KEY: str):
        """コンストラクタ"""
        # APIクライアントを作成
        self.client = build("youtube", "v3", developerKey=API_KEY)

        return

    # デストラクタ
    def __del__(self):
        """デストラクタ"""
        # APIクライアントを削除
        del self.client

        return

    # チャンネルのコンテンツを取得するメソッド
    def top_content(self, channel_id: str, max: int = 10, order: str = "date") -> dict:
        """チャンネルの動画と生放送を取得する

        複数種類のAPIリクエストを投げることでコンテンツの詳細情報を取得している
        """
        contents: dict = {"live": [], "video": []}
        contents["live"]: list = []
        contents["video"]: list = []

        # APIで情報を取得
        items = self._api_request(channel_id, max, order)

        # 情報を辞書にまとめる
        for item in items:
            content = {}
            # 共通部分
            content.update(self._get_common_part(item))
            # 生放送かどうかで分岐
            if "liveStreamingDetails" in item:
                content["type"] = "live"
                content.update(self._get_live_part(item))
            else:
                content["type"] = "video"
            # 辞書に追加
            contents[content["type"]].append(content)

        return contents

    # APIリクエスト
    def _api_request(self, channel_id: str, max: int, order: str):
        items: list = []
        # search().listでchannel_id から検索する
        search_channel = (
            self.client.search().list(channelId=channel_id, part="snippet", maxResults=max, type="video", order=order, safeSearch="none").execute()
        )
        # デバッグ用の出力
        if self.output_api_data:
            with open("search_channel.json", "w", encoding="UTF-8") as f:
                f.write(json.dumps(search_channel, indent=4, ensure_ascii=False))

        # リクエスト数を減らすために video_ids を作成
        video_ids = [item["id"]["videoId"] for item in search_channel["items"]]

        # videos().listでvideo_idsから検索する
        snippet: dict = self.client.videos().list(id=",".join(video_ids), part="snippet").execute()
        statistics: dict = self.client.videos().list(id=",".join(video_ids), part="statistics").execute()
        live_streaming_details: dict = self.client.videos().list(id=",".join(video_ids), part="liveStreamingDetails").execute()
        # デバッグ用の出力
        if self.output_api_data:
            with open("snippet_res.json", "w", encoding="UTF-8") as f:
                f.write(json.dumps(snippet, indent=4, ensure_ascii=False))
            with open("statistics_res.json", "w", encoding="UTF-8") as f:
                f.write(json.dumps(statistics, indent=4, ensure_ascii=False))
            with open("liveStreamingDetails_res.json", "w", encoding="UTF-8") as f:
                f.write(json.dumps(live_streaming_details, indent=4, ensure_ascii=False))

        # レスポンスをまとめる
        for snippet_item, statistics_item, live_streaming_details_item in zip(snippet["items"], statistics["items"], live_streaming_details["items"]):
            item = {}
            item.update(snippet_item)
            item.update(statistics_item)
            item.update(live_streaming_details_item)
            items.append(item)
        # デバッグ用の出力
        if self.output_api_data:
            with open("items.json", "w", encoding="UTF-8") as f:
                f.write(json.dumps(items, indent=4, ensure_ascii=False))

        # 結果を返す
        return items

    # アイテムの共通部分
    def _get_common_part(self, item):
        content = {}
        content["id"] = item["id"]
        content["channel_id"] = item["snippet"]["channelId"]
        content["channel_title"] = item["snippet"]["channelTitle"]
        if "tags" in item["snippet"]:
            content["tags"] = item["snippet"]["tags"]
        else:
            content["tags"] = []
        content["title"] = item["snippet"]["title"]
        content["link"] = "https://www.youtube.com/watch?v=" + item["id"]
        content["description"] = item["snippet"]["description"]
        content["published_at"] = item["snippet"]["publishedAt"]
        # 最初に見つかったサイズのサムネイルを取得する
        for size in self.thumbnail_sizes:
            if size in item["snippet"]["thumbnails"]:
                content["thumbnail_link"] = item["snippet"]["thumbnails"][size]["url"]
                break
        content["view_count"] = int(item["statistics"]["viewCount"])
        content["comment_count"] = int(item["statistics"]["commentCount"])
        content["like_count"] = int(item["statistics"]["likeCount"])

        return content

    # 生放送の情報を取得するメソッド
    def _get_live_part(self, item):
        content = {}
        # 予定開始時刻があれば取得
        if item["liveStreamingDetails"]["scheduledStartTime"] is not None:
            content["scheduled_start_at"] = item["liveStreamingDetails"]["scheduledStartTime"]
        # 放送状況の取得
        if item["snippet"]["liveBroadcastContent"] == "live":  # 配信中の動画
            content["status"] = "now"
            content["actual_start_at"] = item["liveStreamingDetails"]["actualStartTime"]
            content["current_view_count"] = int(item["liveStreamingDetails"]["concurrentViewers"])
        elif item["snippet"]["liveBroadcastContent"] == "upcoming":  # 配信予定の動画
            content["status"] = "future"
        elif item["snippet"]["liveBroadcastContent"] == "none":  # 終了済みの動画
            content["status"] = "past"
            content["actual_start_at"] = item["liveStreamingDetails"]["actualStartTime"]
            content["actual_end_at"] = item["liveStreamingDetails"]["actualEndTime"]

        return content
