from __future__ import print_function

import os
from datetime import datetime, time, timedelta
from pprint import pprint
from shutil import copy, rmtree
from typing import Any, Dict, List
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine.base import Engine


class EdgeHistoryAnalyzer(object):
    def __init__(self) -> None:
        """Analyze your Edge browser history."""
        super().__init__()
        self.username: str = os.getlogin()
        self.EDGE_STORAGE_PATH = f"c:/Users/{self.username}/AppData/Local/Microsoft/Edge/User Data/Default"
        self.LOCAL_STORAGE_PATH = os.path.abspath(f"./data/tmp")
        self.LOCAL_STORAGE_ROOT = os.path.abspath("./data")

        # Try deleting temporary data
        try:
            self.__del_file(os.path.abspath(self.LOCAL_STORAGE_PATH))
        except FileNotFoundError:
            pass
        try:
            rmtree(self.LOCAL_STORAGE_ROOT)
        except FileNotFoundError:
            pass

        # Prepare database
        if not os.path.isdir(self.LOCAL_STORAGE_PATH):
            os.makedirs(self.LOCAL_STORAGE_PATH)
        files: List[str] = os.listdir(self.EDGE_STORAGE_PATH)
        for file in files:
            if not os.path.isdir(os.path.join(self.EDGE_STORAGE_PATH, file)):
                copy(os.path.join(self.EDGE_STORAGE_PATH, file),
                     self.LOCAL_STORAGE_PATH)

        # Connect to the database
        self.history_db: Engine = create_engine(
            "sqlite:///data/tmp/History", future=True)
        self.history: List[Dict[str, str]] = []

        # Preprocess the history data
        with self.history_db.connect() as conn:
            history_ = conn.execute(text("SELECT * FROM urls"))
            for his in history_:
                self.history.append(
                    {
                        "id": his[0],
                        "url": his[1],
                        "title": his[2],
                        "visit_count": his[3],
                        "typed_count": his[4],
                        "last_visit_time": self.__convert_webkit_time(his[5]),
                        "hiddens": his[6]
                    }
                )
        # sort the history in order to make it easier to fetch most visited urls
        self.history.sort(key=lambda x: x["visit_count"], reverse=True)

    def __del_file(self, path_data: str) -> None:
        """Delete files recursively

        Args:
            path_data (str): The directory to delete
        """
        for i in os.listdir(path_data):
            file_data: str = path_data + "\\" + i
            if os.path.isfile(file_data) == True:
                os.remove(file_data)
            else:
                self.__del_file(file_data)

    def __convert_webkit_time(self, webkit_timestamp: int) -> datetime:
        """Convert webkit timestamps to Python datetime objects

        Args:
            webkit_timestamp (int): the webkit timestamp to convert

        Returns:
            datetime: the converted datetime object
        """
        epoch_start: datetime = datetime(
            1601, 1, 1)  # webkit timestamp starts from 1601.1.1
        delta: timedelta = timedelta(microseconds=int(webkit_timestamp))
        return epoch_start + delta

    def __calculate_url_visits(self) -> Dict[str, Any]:
        """Analyze visited urls and calculate the total number of visited times

        Returns:
            Dict[str, Any]: Analyzed results
        """
        cnt = 0
        maxn = {"visit_count": 0}
        for his in self.history:
            cnt += his["visit_count"]
            maxn = his if his["visit_count"] > maxn["visit_count"] else maxn
        return {
            "total_visits": cnt,
            "most_visited": maxn
        }

    def __calculate_site_visits(self) -> Dict[str, Any]:
        """Analyze visited sites and calculate the total number of visited times

        Returns:
            Dict[str, Any]: Analyzed results
        """
        cnt = 0
        maxn = {"visit_count": 0}
        history_sites = []
        for his in self.history:
            found = False
            for site in history_sites:
                if urlparse(his["url"]).hostname == site["domain"]:
                    site["visit_count"] += his["visit_count"]
                    site["last_visit_time"] = his["last_visit_time"] if his["last_visit_time"] > site["last_visit_time"] else site["last_visit_time"]
                    maxn = site if site["visit_count"] > maxn["visit_count"] else maxn
                    found = True
                    break
            if not found:  # needed to create a new site
                history_sites.append({
                    "domain": urlparse(his["url"]).hostname,
                    "visit_count": his["visit_count"],
                    "last_visit_time": his["last_visit_time"]
                })
                cnt += 1
        history_sites.sort(key=lambda x: x["visit_count"], reverse=True)
        return {
            "total_visited_sites": cnt,
            "most_visited_site": maxn,
            "visited_sites": history_sites
        }

    def analyze(self) -> Dict[str, Any]:
        """Analyze your browser's history.

        Note: This function will not upload your personal information.

        Returns:
            Dict[str, Any]: the analyzed results
        """
        url_visits = self.__calculate_url_visits()
        site_visits = self.__calculate_site_visits()
        return {
            "total_visited_urls": len(self.history),
            "total_viewed_urls": url_visits["total_visits"],
            "most_visited_urls": self.history[:5],
            "total_visited_sites": len(site_visits["visited_sites"]),
            "total_viewed_sites": site_visits["total_visited_sites"],
            "most_visited_sites": site_visits["visited_sites"][:5]
        }
