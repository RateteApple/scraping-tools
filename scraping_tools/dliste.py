# coding: utf-8

from __future__ import annotations
from datetime import datetime, timedelta
import time
import re
from pprint import pprint
import json
import unicodedata

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement

options = webdriver.ChromeOptions()
options.add_argument("--no-sandbox")
# options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

class DLsite:
    """DLsiteのページから情報を取得するクラス"""

    @staticmethod
    def work(work_id:str) -> str:
        """DLsiteの作品ページから情報を取得する
        
        Args:
            work_id (str): 作品ID
        
        Returns:
            str: json形式の文字列
        """
        work = {}
        # ブラウザを開く
        driver = webdriver.Chrome(options=options)
        # ページを開く
        driver.get(f"https://www.dlsite.com/maniax/work/=/product_id/{work_id}.html")
        # 読み込みが終わるまで待機
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//div")))

        # 正常なページか判定
        if "エラー" in driver.title:
            driver.quit()
            raise ValueError("DLsiteの作品ページが見つかりませんでした。")
        
        # 作品情報を取得
        work["id"]:str = work_id
        work["title"]:str = driver.title
        work["link"]:str = driver.current_url
        work["discription"]:str = driver.find_element(By.XPATH, '//div[@itemprop="description"]').text
        work["maker_name"]:str = driver.find_element(By.XPATH, '//span[@class="maker_name"]').text
        maker_link:str = driver.find_element(By.XPATH, '//span[@class="maker_name"]/a').get_attribute("href")
        work["maker_id"]:str = maker_link.split('/')[-1].replace('.html', '')
        work["sale_number"]:int = int(driver.find_element(By.XPATH, '//dd[@class="point"]').text.replace(',', ''))
        work["average_rate"]:float = float(driver.find_element(By.XPATH, '//span[@class="point average_count"]').text)
        work["rate_count"]:int = int(driver.find_element(By.XPATH, '//div[@class="star_wrap"]/span[@class="count"]').text.replace('(', '').replace(')', ''))
        work["favarite_count"]:int = int(driver.find_element(By.XPATH, '//dd[@class="position_fix"]').text.replace(',', ''))

        # Unicode正規化
        work = {key: unicodedata.normalize("NFKC", value) if isinstance(value, str) else value for key, value in work.items()}
        # JSON形式に変換
        work_json:str = json.dumps(work, ensure_ascii=False, indent=4)

        # ブラウザを閉じる
        driver.quit()

        return work_json
    

if __name__ == "__main__":
    work_id:str = "RJ01077937"
    work_json:str = DLsite.work(work_id)
    pprint(work_json)