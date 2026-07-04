# pypi_finder.py
# -*- coding: utf-8 -*-

"""
PyPI 官方資料探索器

用途：
當 crawler.py 裡沒有某個第三方套件的固定官方文件來源時，
先用 PyPI JSON API 找這個套件的 Documentation / Docs / Homepage。

優先順序：
1. project_urls 裡的 Documentation / Docs / API / Reference
2. project_urls 裡的 Homepage / Source
3. info.home_page
4. PyPI 專案頁
"""

import requests


# 使用者常打的名字，和 PyPI 套件名稱有時不同
PYPI_NAME_ALIASES = {
    "bs4": "beautifulsoup4",
    "beautifulsoup": "beautifulsoup4",
    "beautifulsoup4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "scikit_learn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "dotenv": "python-dotenv",
    "python_dotenv": "python-dotenv",
    "pyqt": "PyQt6",
    "pyqt6": "PyQt6",
    "google-generativeai": "google-generativeai",
    "google_genai": "google-generativeai",
}


def normalize_pypi_name(package_name):
    """
    將使用者輸入轉成比較可能的 PyPI 套件名稱。
    """

    key = package_name.strip().lower().replace(" ", "-")

    return PYPI_NAME_ALIASES.get(key, package_name.strip())


def get_pypi_json(package_name):
    """
    從 PyPI JSON API 取得套件資料。
    """

    pypi_name = normalize_pypi_name(package_name)
    url = f"https://pypi.org/pypi/{pypi_name}/json"

    response = requests.get(url, timeout=10)

    if response.status_code != 200:
        return None

    return response.json()


def pick_documentation_url(info):
    """
    從 PyPI info 裡挑出最像官方文件的網址。
    """

    project_urls = info.get("project_urls") or {}

    # title 關鍵字優先
    title_priority = [
        "documentation",
        "docs",
        "doc",
        "api",
        "reference",
        "user guide",
        "homepage",
        "home",
        "source",
    ]

    for keyword in title_priority:
        for title, url in project_urls.items():
            if keyword in title.lower():
                return url

    # url 關鍵字次之
    url_priority = [
        "readthedocs",
        "docs",
        "documentation",
        "api",
        "reference",
    ]

    for keyword in url_priority:
        for url in project_urls.values():
            if keyword in url.lower():
                return url

    home_page = info.get("home_page") or ""

    if home_page:
        return home_page

    return ""


def pick_homepage_url(info):
    """
    取得首頁網址。
    """

    home_page = info.get("home_page") or ""

    if home_page:
        return home_page

    project_urls = info.get("project_urls") or {}

    for title, url in project_urls.items():
        if "home" in title.lower() or "homepage" in title.lower():
            return url

    return ""


def discover_package_from_pypi(package_name):
    """
    對外主函式。

    回傳格式：
    {
        "input_name": 使用者輸入,
        "pypi_name": PyPI 套件名,
        "summary": 套件摘要,
        "doc_url": 文件網址,
        "homepage_url": 首頁網址,
        "pypi_url": PyPI 專案頁
    }

    找不到時回傳 None。
    """

    data = get_pypi_json(package_name)

    if data is None:
        return None

    info = data.get("info", {})
    pypi_name = info.get("name") or normalize_pypi_name(package_name)
    summary = info.get("summary") or ""
    pypi_url = info.get("package_url") or f"https://pypi.org/project/{pypi_name}/"

    doc_url = pick_documentation_url(info)
    homepage_url = pick_homepage_url(info)

    if not doc_url:
        doc_url = pypi_url

    return {
        "input_name": package_name,
        "pypi_name": pypi_name,
        "summary": summary,
        "doc_url": doc_url,
        "homepage_url": homepage_url,
        "pypi_url": pypi_url,
    }
