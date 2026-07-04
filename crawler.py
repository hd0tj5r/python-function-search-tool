# crawler.py
# -*- coding: utf-8 -*-

"""
按需爬蟲、官方文件來源、PyPI 整合層

支援：
1. Python 標準函式庫繁中官方文件
2. 常用第三方套件官方文件來源 + fallback
3. 未知第三方套件：用 PyPI JSON API 找官方文件入口

注意：
第三方套件官方網站 HTML 結構差異很大，
所以本版先採「官方來源網址 + 常用函式補充資料」。
如果沒有專用解析器，就先存「官方文件入口」。
"""

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from database import FunctionEnter
from pypi_finder import discover_package_from_pypi, normalize_pypi_name


PYTHON_BASE_URL = "https://docs.python.org/zh-tw/3/library/"


PYTHON_DOC_PAGES = [
    {
        "url": urljoin(PYTHON_BASE_URL, "functions.html"),
        "default_package": "builtins",
        "category": "內建函式"
    },
    {
        "url": urljoin(PYTHON_BASE_URL, "stdtypes.html"),
        "default_package": "built-in types",
        "category": "內建型別方法"
    },
    {
        "url": urljoin(PYTHON_BASE_URL, "collections.html"),
        "default_package": "collections",
        "category": "容器工具"
    },
    {
        "url": urljoin(PYTHON_BASE_URL, "math.html"),
        "default_package": "math",
        "category": "數學運算"
    },
    {
        "url": urljoin(PYTHON_BASE_URL, "statistics.html"),
        "default_package": "statistics",
        "category": "統計運算"
    },
]


# 固定官方文件來源表。
# 若找不到，才交給 PyPI 自動探索。
OFFICIAL_DOC_SOURCES = {
    "python": "https://docs.python.org/zh-tw/3/library/index.html",
    "numpy": "https://numpy.org/doc/stable/reference/",
    "pandas": "https://pandas.pydata.org/docs/reference/index.html",
    "matplotlib": "https://matplotlib.org/stable/api/index.html",
    "sklearn": "https://scikit-learn.org/stable/api/index.html",
    "scikit-learn": "https://scikit-learn.org/stable/api/index.html",

    "seaborn": "https://seaborn.pydata.org/api.html",
    "tensorflow": "https://www.tensorflow.org/api_docs/python/tf",
    "requests": "https://requests.readthedocs.io/en/latest/api/",
    "beautifulsoup4": "https://www.crummy.com/software/BeautifulSoup/bs4/doc/",
    "beautifulsoup": "https://www.crummy.com/software/BeautifulSoup/bs4/doc/",
    "bs4": "https://www.crummy.com/software/BeautifulSoup/bs4/doc/",
    "selenium": "https://www.selenium.dev/selenium/docs/api/py/api.html",
    "django": "https://docs.djangoproject.com/en/stable/ref/",
    "flask": "https://flask.palletsprojects.com/en/stable/api/",
    "fastapi": "https://fastapi.tiangolo.com/reference/",
    "google-generativeai": "https://ai.google.dev/api/python/google/generativeai",
    "gspread": "https://docs.gspread.org/en/latest/api/",
    "google-cloud-storage": "https://cloud.google.com/python/docs/reference/storage/latest",
    "google-api-python-client": "https://googleapis.github.io/google-api-python-client/docs/",
    "pyqt6": "https://www.riverbankcomputing.com/static/Docs/PyQt6/",
    "openpyxl": "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.html",
    "reportlab": "https://docs.reportlab.com/reportlab/userguide/ch1_intro/",
    "celery": "https://docs.celeryq.dev/en/stable/reference/",
    "python-dotenv": "https://saurabh-kumar.com/python-dotenv/reference/",
    "dotenv": "https://saurabh-kumar.com/python-dotenv/reference/",
}


PACKAGE_ALIASES = {
    "beautifulsoup": "beautifulsoup4",
    "bs4": "beautifulsoup4",
    "scikit_learn": "sklearn",
    "scikit-learn": "sklearn",
    "dotenv": "python-dotenv",
    "python_dotenv": "python-dotenv",
    "pyqt": "PyQt6",
    "pyqt6": "PyQt6",
}


def canonical_package_name(package_name):
    key = package_name.strip().lower()

    return PACKAGE_ALIASES.get(key, package_name.strip())


BUILTIN_FALLBACK_DATA = [
    ("list", "append", "內建型別方法", "把一個元素加到串列最後面。", "list.append"),
    ("list", "extend", "內建型別方法", "把另一個可疊代資料中的所有元素加到串列最後面。", "list.extend"),
    ("list", "insert", "內建型別方法", "在指定位置插入一個元素。", "list.insert"),
    ("list", "remove", "內建型別方法", "移除串列中第一個符合指定值的元素。", "list.remove"),
    ("list", "pop", "內建型別方法", "移除並回傳指定位置的元素；未指定時通常移除最後一個。", "list.pop"),
    ("list", "clear", "內建型別方法", "清空串列中的所有元素。", "list.clear"),
    ("list", "index", "內建型別方法", "找出某個元素第一次出現的位置。", "list.index"),
    ("list", "count", "內建型別方法", "計算某個元素在串列中出現幾次。", "list.count"),
    ("list", "sort", "內建型別方法", "將串列本身排序，會直接改變原本串列。", "list.sort"),
    ("list", "reverse", "內建型別方法", "將串列中的元素順序反轉。", "list.reverse"),
    ("list", "copy", "內建型別方法", "回傳串列的淺層複製。", "list.copy"),

    ("dict", "keys", "內建型別方法", "取得字典中所有 key 的檢視物件。", "dict.keys"),
    ("dict", "values", "內建型別方法", "取得字典中所有 value 的檢視物件。", "dict.values"),
    ("dict", "items", "內建型別方法", "取得字典中所有 key 和 value 配對的檢視物件。", "dict.items"),
    ("dict", "get", "內建型別方法", "用 key 取得 value；如果 key 不存在，可回傳預設值。", "dict.get"),
    ("dict", "update", "內建型別方法", "更新字典內容，或加入新的 key-value 資料。", "dict.update"),
    ("dict", "pop", "內建型別方法", "移除指定 key，並回傳對應的 value。", "dict.pop"),
    ("dict", "clear", "內建型別方法", "清空字典中的所有資料。", "dict.clear"),

    ("str", "split", "內建型別方法", "依照指定分隔符號切割字串，回傳串列。", "str.split"),
    ("str", "strip", "內建型別方法", "移除字串前後的空白或指定字元。", "str.strip"),
    ("str", "replace", "內建型別方法", "把字串中的指定內容替換成新的內容。", "str.replace"),
    ("str", "lower", "內建型別方法", "把字串轉成小寫。", "str.lower"),
    ("str", "upper", "內建型別方法", "把字串轉成大寫。", "str.upper"),
    ("str", "find", "內建型別方法", "尋找子字串第一次出現的位置；找不到會回傳 -1。", "str.find"),
    ("str", "startswith", "內建型別方法", "判斷字串是否以指定內容開頭。", "str.startswith"),
    ("str", "endswith", "內建型別方法", "判斷字串是否以指定內容結尾。", "str.endswith"),
    ("str", "join", "內建型別方法", "把多個字串用指定符號連接起來。", "str.join"),
    ("str", "format", "內建型別方法", "把資料帶入字串格式中。", "str.format"),

    ("set", "add", "內建型別方法", "把一個元素加入集合。", "set.add"),
    ("set", "remove", "內建型別方法", "從集合中移除指定元素；元素不存在時會出錯。", "set.remove"),
    ("set", "discard", "內建型別方法", "從集合中移除指定元素；元素不存在時不會出錯。", "set.discard"),
    ("set", "pop", "內建型別方法", "從集合中移除並回傳一個元素。", "set.pop"),
    ("set", "clear", "內建型別方法", "清空集合中的所有元素。", "set.clear"),
]


# 欄位：package, name, category, description_zh, source_url, source_anchor
THIRD_PARTY_FALLBACK_DATA = [
    # NumPy
    ("numpy", "array", "NumPy 陣列建立", "建立 NumPy 陣列，是 NumPy 最常用的資料結構。", "https://numpy.org/doc/stable/reference/generated/numpy.array.html", "numpy.array"),
    ("numpy", "arange", "NumPy 陣列建立", "產生一段等距數值，類似 Python 的 range，但回傳 NumPy 陣列。", "https://numpy.org/doc/stable/reference/generated/numpy.arange.html", "numpy.arange"),
    ("numpy", "linspace", "NumPy 陣列建立", "在指定範圍內產生固定數量的等距數值。", "https://numpy.org/doc/stable/reference/generated/numpy.linspace.html", "numpy.linspace"),
    ("numpy", "zeros", "NumPy 陣列建立", "建立全部元素都是 0 的陣列。", "https://numpy.org/doc/stable/reference/generated/numpy.zeros.html", "numpy.zeros"),
    ("numpy", "ones", "NumPy 陣列建立", "建立全部元素都是 1 的陣列。", "https://numpy.org/doc/stable/reference/generated/numpy.ones.html", "numpy.ones"),
    ("numpy", "reshape", "NumPy 陣列操作", "改變陣列形狀，但資料總數必須相同。", "https://numpy.org/doc/stable/reference/generated/numpy.reshape.html", "numpy.reshape"),
    ("numpy", "mean", "NumPy 統計運算", "計算平均值。", "https://numpy.org/doc/stable/reference/generated/numpy.mean.html", "numpy.mean"),
    ("numpy", "sum", "NumPy 統計運算", "計算總和。", "https://numpy.org/doc/stable/reference/generated/numpy.sum.html", "numpy.sum"),
    ("numpy", "max", "NumPy 統計運算", "取得最大值。", "https://numpy.org/doc/stable/reference/generated/numpy.max.html", "numpy.max"),
    ("numpy", "min", "NumPy 統計運算", "取得最小值。", "https://numpy.org/doc/stable/reference/generated/numpy.min.html", "numpy.min"),
    ("numpy", "std", "NumPy 統計運算", "計算標準差。", "https://numpy.org/doc/stable/reference/generated/numpy.std.html", "numpy.std"),
    ("numpy", "where", "NumPy 條件篩選", "依條件選擇資料或找出符合條件的位置。", "https://numpy.org/doc/stable/reference/generated/numpy.where.html", "numpy.where"),

    # pandas
    ("pandas", "DataFrame", "pandas 資料結構", "建立表格型資料，類似 Excel 表格或資料庫資料表。", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html", "pandas.DataFrame"),
    ("pandas", "Series", "pandas 資料結構", "建立一維資料，類似有索引的一欄資料。", "https://pandas.pydata.org/docs/reference/api/pandas.Series.html", "pandas.Series"),
    ("pandas", "read_csv", "pandas 資料讀取", "讀取 CSV 檔案並轉成 DataFrame。", "https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html", "pandas.read_csv"),
    ("pandas", "read_excel", "pandas 資料讀取", "讀取 Excel 檔案並轉成 DataFrame。", "https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html", "pandas.read_excel"),
    ("pandas", "head", "pandas 資料查看", "查看 DataFrame 前幾筆資料。", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.head.html", "pandas.DataFrame.head"),
    ("pandas", "tail", "pandas 資料查看", "查看 DataFrame 後幾筆資料。", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.tail.html", "pandas.DataFrame.tail"),
    ("pandas", "info", "pandas 資料查看", "查看欄位、資料型別與缺失值概況。", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.info.html", "pandas.DataFrame.info"),
    ("pandas", "describe", "pandas 統計摘要", "快速產生數值欄位的統計摘要。", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.describe.html", "pandas.DataFrame.describe"),
    ("pandas", "groupby", "pandas 分組統計", "依照欄位分組後進行統計或運算。", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.groupby.html", "pandas.DataFrame.groupby"),
    ("pandas", "merge", "pandas 資料合併", "依照共同欄位合併兩個 DataFrame。", "https://pandas.pydata.org/docs/reference/api/pandas.merge.html", "pandas.merge"),
    ("pandas", "dropna", "pandas 缺失值處理", "移除含有缺失值的資料列或欄。", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.dropna.html", "pandas.DataFrame.dropna"),
    ("pandas", "fillna", "pandas 缺失值處理", "用指定值填補缺失值。", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.fillna.html", "pandas.DataFrame.fillna"),

    # Matplotlib
    ("matplotlib", "plot", "Matplotlib 視覺化", "畫折線圖，常用來觀察趨勢。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.plot.html", "matplotlib.pyplot.plot"),
    ("matplotlib", "scatter", "Matplotlib 視覺化", "畫散佈圖，常用來觀察兩個數值之間的關係。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html", "matplotlib.pyplot.scatter"),
    ("matplotlib", "bar", "Matplotlib 視覺化", "畫長條圖，常用來比較不同類別的數值。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.bar.html", "matplotlib.pyplot.bar"),
    ("matplotlib", "hist", "Matplotlib 視覺化", "畫直方圖，常用來觀察資料分布。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.hist.html", "matplotlib.pyplot.hist"),
    ("matplotlib", "xlabel", "Matplotlib 圖表設定", "設定 x 軸標籤。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.xlabel.html", "matplotlib.pyplot.xlabel"),
    ("matplotlib", "ylabel", "Matplotlib 圖表設定", "設定 y 軸標籤。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.ylabel.html", "matplotlib.pyplot.ylabel"),
    ("matplotlib", "title", "Matplotlib 圖表設定", "設定圖表標題。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.title.html", "matplotlib.pyplot.title"),
    ("matplotlib", "legend", "Matplotlib 圖表設定", "顯示圖例。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.legend.html", "matplotlib.pyplot.legend"),
    ("matplotlib", "show", "Matplotlib 圖表顯示", "顯示目前建立的圖表。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.show.html", "matplotlib.pyplot.show"),
    ("matplotlib", "subplots", "Matplotlib 圖表建立", "建立 Figure 和 Axes，適合較正式的畫圖方式。", "https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.subplots.html", "matplotlib.pyplot.subplots"),

    # scikit-learn
    ("sklearn", "train_test_split", "scikit-learn 資料切分", "將資料切分成訓練集與測試集。", "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html", "sklearn.model_selection.train_test_split"),
    ("sklearn", "StandardScaler", "scikit-learn 前處理", "將特徵標準化，讓平均值接近 0、標準差接近 1。", "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html", "sklearn.preprocessing.StandardScaler"),
    ("sklearn", "MinMaxScaler", "scikit-learn 前處理", "將特徵縮放到指定範圍，常見是 0 到 1。", "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html", "sklearn.preprocessing.MinMaxScaler"),
    ("sklearn", "LinearRegression", "scikit-learn 迴歸模型", "線性迴歸模型，用來預測連續數值。", "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html", "sklearn.linear_model.LinearRegression"),
    ("sklearn", "LogisticRegression", "scikit-learn 分類模型", "邏輯斯迴歸模型，常用於分類問題。", "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html", "sklearn.linear_model.LogisticRegression"),
    ("sklearn", "DecisionTreeClassifier", "scikit-learn 分類模型", "決策樹分類模型。", "https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeClassifier.html", "sklearn.tree.DecisionTreeClassifier"),
    ("sklearn", "RandomForestClassifier", "scikit-learn 分類模型", "隨機森林分類模型，由多棵決策樹組成。", "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html", "sklearn.ensemble.RandomForestClassifier"),
    ("sklearn", "KMeans", "scikit-learn 分群模型", "K 平均分群演算法，用來把資料分成 K 群。", "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html", "sklearn.cluster.KMeans"),
    ("sklearn", "accuracy_score", "scikit-learn 評估指標", "計算分類模型預測正確率。", "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.accuracy_score.html", "sklearn.metrics.accuracy_score"),
    ("sklearn", "confusion_matrix", "scikit-learn 評估指標", "建立混淆矩陣，用來觀察分類結果。", "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.confusion_matrix.html", "sklearn.metrics.confusion_matrix"),

    # seaborn
    ("seaborn", "set_theme", "Seaborn 樣式設定", "設定 seaborn 的整體圖表風格。", "https://seaborn.pydata.org/generated/seaborn.set_theme.html", "seaborn.set_theme"),
    ("seaborn", "load_dataset", "Seaborn 資料集", "載入 seaborn 內建範例資料集。", "https://seaborn.pydata.org/generated/seaborn.load_dataset.html", "seaborn.load_dataset"),
    ("seaborn", "scatterplot", "Seaborn 視覺化", "繪製散佈圖，適合觀察兩個數值變數的關係。", "https://seaborn.pydata.org/generated/seaborn.scatterplot.html", "seaborn.scatterplot"),
    ("seaborn", "lineplot", "Seaborn 視覺化", "繪製折線圖，適合觀察趨勢。", "https://seaborn.pydata.org/generated/seaborn.lineplot.html", "seaborn.lineplot"),
    ("seaborn", "barplot", "Seaborn 視覺化", "繪製長條圖，適合比較不同類別的數值。", "https://seaborn.pydata.org/generated/seaborn.barplot.html", "seaborn.barplot"),
    ("seaborn", "histplot", "Seaborn 視覺化", "繪製直方圖，適合觀察資料分布。", "https://seaborn.pydata.org/generated/seaborn.histplot.html", "seaborn.histplot"),
    ("seaborn", "boxplot", "Seaborn 視覺化", "繪製盒鬚圖，適合觀察分布與離群值。", "https://seaborn.pydata.org/generated/seaborn.boxplot.html", "seaborn.boxplot"),
    ("seaborn", "heatmap", "Seaborn 視覺化", "繪製熱力圖，常用於相關係數或矩陣資料。", "https://seaborn.pydata.org/generated/seaborn.heatmap.html", "seaborn.heatmap"),
    ("seaborn", "pairplot", "Seaborn 視覺化", "快速觀察多個欄位兩兩之間的關係。", "https://seaborn.pydata.org/generated/seaborn.pairplot.html", "seaborn.pairplot"),

    # TensorFlow
    ("tensorflow", "constant", "TensorFlow 張量", "建立 TensorFlow 常數張量。", "https://www.tensorflow.org/api_docs/python/tf/constant", "tf.constant"),
    ("tensorflow", "Variable", "TensorFlow 變數", "建立可訓練或可更新的 TensorFlow 變數。", "https://www.tensorflow.org/api_docs/python/tf/Variable", "tf.Variable"),
    ("tensorflow", "keras.Sequential", "TensorFlow Keras", "用線性堆疊方式建立神經網路模型。", "https://www.tensorflow.org/api_docs/python/tf/keras/Sequential", "tf.keras.Sequential"),
    ("tensorflow", "keras.layers.Dense", "TensorFlow Keras", "建立全連接層，常用於神經網路。", "https://www.tensorflow.org/api_docs/python/tf/keras/layers/Dense", "tf.keras.layers.Dense"),
    ("tensorflow", "keras.Model", "TensorFlow Keras", "Keras 模型基底類別。", "https://www.tensorflow.org/api_docs/python/tf/keras/Model", "tf.keras.Model"),
    ("tensorflow", "keras.optimizers.Adam", "TensorFlow Keras", "Adam 最佳化器，常用於訓練神經網路。", "https://www.tensorflow.org/api_docs/python/tf/keras/optimizers/Adam", "tf.keras.optimizers.Adam"),
    ("tensorflow", "data.Dataset", "TensorFlow 資料集", "建立資料管線，常用於模型訓練資料輸入。", "https://www.tensorflow.org/api_docs/python/tf/data/Dataset", "tf.data.Dataset"),
    ("tensorflow", "GradientTape", "TensorFlow 自動微分", "記錄運算以計算梯度。", "https://www.tensorflow.org/api_docs/python/tf/GradientTape", "tf.GradientTape"),
    ("tensorflow", "reduce_mean", "TensorFlow 運算", "計算張量指定維度的平均值。", "https://www.tensorflow.org/api_docs/python/tf/reduce_mean", "tf.reduce_mean"),

    # requests
    ("requests", "get", "requests HTTP", "發送 HTTP GET 請求，常用於取得網頁或 API 資料。", "https://requests.readthedocs.io/en/latest/api/#requests.get", "requests.get"),
    ("requests", "post", "requests HTTP", "發送 HTTP POST 請求，常用於送出表單或 JSON 資料。", "https://requests.readthedocs.io/en/latest/api/#requests.post", "requests.post"),
    ("requests", "put", "requests HTTP", "發送 HTTP PUT 請求，常用於更新資料。", "https://requests.readthedocs.io/en/latest/api/#requests.put", "requests.put"),
    ("requests", "delete", "requests HTTP", "發送 HTTP DELETE 請求，常用於刪除資料。", "https://requests.readthedocs.io/en/latest/api/#requests.delete", "requests.delete"),
    ("requests", "Session", "requests 工作階段", "建立可重複使用連線與共用設定的請求工作階段。", "https://requests.readthedocs.io/en/latest/api/#request-sessions", "requests.Session"),
    ("requests", "Response", "requests 回應", "HTTP 回應物件，包含狀態碼、文字、JSON 等資料。", "https://requests.readthedocs.io/en/latest/api/#requests.Response", "requests.Response"),

    # BeautifulSoup
    ("beautifulsoup4", "BeautifulSoup", "BeautifulSoup 解析", "建立 BeautifulSoup 物件，用來解析 HTML 或 XML。", "https://www.crummy.com/software/BeautifulSoup/bs4/doc/#beautifulsoup", "bs4.BeautifulSoup"),
    ("beautifulsoup4", "find", "BeautifulSoup 搜尋", "尋找第一個符合條件的標籤。", "https://www.crummy.com/software/BeautifulSoup/bs4/doc/#find", "bs4.find"),
    ("beautifulsoup4", "find_all", "BeautifulSoup 搜尋", "尋找所有符合條件的標籤。", "https://www.crummy.com/software/BeautifulSoup/bs4/doc/#find-all", "bs4.find_all"),
    ("beautifulsoup4", "select", "BeautifulSoup CSS 選擇器", "使用 CSS selector 搜尋標籤。", "https://www.crummy.com/software/BeautifulSoup/bs4/doc/#css-selectors", "bs4.select"),
    ("beautifulsoup4", "get_text", "BeautifulSoup 文字", "取得標籤中的文字內容。", "https://www.crummy.com/software/BeautifulSoup/bs4/doc/#get-text", "bs4.get_text"),
    ("beautifulsoup4", "prettify", "BeautifulSoup 格式化", "把 HTML 結構整理成較容易閱讀的格式。", "https://www.crummy.com/software/BeautifulSoup/bs4/doc/#pretty-printing", "bs4.prettify"),

    # Selenium
    ("selenium", "webdriver.Chrome", "Selenium 瀏覽器", "啟動 Chrome WebDriver，自動控制瀏覽器。", "https://www.selenium.dev/selenium/docs/api/py/webdriver_chrome/selenium.webdriver.chrome.webdriver.html", "selenium.webdriver.Chrome"),
    ("selenium", "get", "Selenium 導航", "讓瀏覽器開啟指定網址。", "https://www.selenium.dev/selenium/docs/api/py/webdriver_remote/selenium.webdriver.remote.webdriver.html", "driver.get"),
    ("selenium", "find_element", "Selenium 元素定位", "尋找第一個符合條件的網頁元素。", "https://www.selenium.dev/selenium/docs/api/py/webdriver_remote/selenium.webdriver.remote.webdriver.html", "driver.find_element"),
    ("selenium", "find_elements", "Selenium 元素定位", "尋找所有符合條件的網頁元素。", "https://www.selenium.dev/selenium/docs/api/py/webdriver_remote/selenium.webdriver.remote.webdriver.html", "driver.find_elements"),
    ("selenium", "click", "Selenium 互動", "點擊網頁元素。", "https://www.selenium.dev/selenium/docs/api/py/webdriver_remote/selenium.webdriver.remote.webelement.html", "element.click"),
    ("selenium", "send_keys", "Selenium 互動", "向輸入框或元素輸入文字。", "https://www.selenium.dev/selenium/docs/api/py/webdriver_remote/selenium.webdriver.remote.webelement.html", "element.send_keys"),
    ("selenium", "WebDriverWait", "Selenium 等待", "等待指定條件成立後再繼續執行。", "https://www.selenium.dev/selenium/docs/api/py/webdriver_support/selenium.webdriver.support.wait.html", "selenium.webdriver.support.ui.WebDriverWait"),
    ("selenium", "By", "Selenium 定位器", "指定元素定位方式，例如 ID、CSS_SELECTOR、XPATH。", "https://www.selenium.dev/selenium/docs/api/py/webdriver_common/selenium.webdriver.common.by.html", "selenium.webdriver.common.by.By"),

    # Django
    ("django", "Model", "Django ORM", "定義資料庫模型。", "https://docs.djangoproject.com/en/stable/topics/db/models/", "django.db.models.Model"),
    ("django", "CharField", "Django ORM", "定義文字欄位。", "https://docs.djangoproject.com/en/stable/ref/models/fields/#charfield", "django.db.models.CharField"),
    ("django", "path", "Django URL", "定義 URL 路由規則。", "https://docs.djangoproject.com/en/stable/ref/urls/#path", "django.urls.path"),
    ("django", "render", "Django View", "回傳套用模板後的 HTTP 回應。", "https://docs.djangoproject.com/en/stable/topics/http/shortcuts/#render", "django.shortcuts.render"),
    ("django", "redirect", "Django View", "重新導向到指定網址或 view。", "https://docs.djangoproject.com/en/stable/topics/http/shortcuts/#redirect", "django.shortcuts.redirect"),
    ("django", "HttpResponse", "Django Response", "建立 HTTP 回應。", "https://docs.djangoproject.com/en/stable/ref/request-response/#httpresponse-objects", "django.http.HttpResponse"),
    ("django", "QuerySet.filter", "Django ORM", "依條件查詢資料。", "https://docs.djangoproject.com/en/stable/ref/models/querysets/#filter", "QuerySet.filter"),

    # Flask & FastAPI
    ("flask", "Flask", "Flask App", "建立 Flask 應用程式物件。", "https://flask.palletsprojects.com/en/stable/api/#flask.Flask", "flask.Flask"),
    ("flask", "route", "Flask 路由", "設定 URL 路由與對應函式。", "https://flask.palletsprojects.com/en/stable/api/#flask.Flask.route", "Flask.route"),
    ("flask", "render_template", "Flask 模板", "渲染 HTML 模板。", "https://flask.palletsprojects.com/en/stable/api/#flask.render_template", "flask.render_template"),
    ("flask", "request", "Flask Request", "取得目前 HTTP 請求資料。", "https://flask.palletsprojects.com/en/stable/api/#flask.request", "flask.request"),
    ("flask", "jsonify", "Flask JSON", "回傳 JSON 格式的 HTTP 回應。", "https://flask.palletsprojects.com/en/stable/api/#flask.json.jsonify", "flask.jsonify"),
    ("fastapi", "FastAPI", "FastAPI App", "建立 FastAPI 應用程式物件。", "https://fastapi.tiangolo.com/reference/fastapi/", "fastapi.FastAPI"),
    ("fastapi", "get", "FastAPI 路由", "建立 GET API 路由。", "https://fastapi.tiangolo.com/tutorial/first-steps/", "FastAPI.get"),
    ("fastapi", "post", "FastAPI 路由", "建立 POST API 路由。", "https://fastapi.tiangolo.com/tutorial/body/", "FastAPI.post"),
    ("fastapi", "Query", "FastAPI 參數", "定義查詢參數的驗證與說明。", "https://fastapi.tiangolo.com/reference/parameters/", "fastapi.Query"),
    ("fastapi", "Path", "FastAPI 參數", "定義路徑參數的驗證與說明。", "https://fastapi.tiangolo.com/reference/parameters/", "fastapi.Path"),
    ("fastapi", "HTTPException", "FastAPI 錯誤", "主動回傳 HTTP 錯誤狀態。", "https://fastapi.tiangolo.com/reference/exceptions/", "fastapi.HTTPException"),
    ("fastapi", "Depends", "FastAPI 依賴注入", "宣告依賴函式，用於驗證、資料庫連線等。", "https://fastapi.tiangolo.com/tutorial/dependencies/", "fastapi.Depends"),
    ("fastapi", "APIRouter", "FastAPI 路由模組", "把多個 API 路由整理成模組。", "https://fastapi.tiangolo.com/reference/apirouter/", "fastapi.APIRouter"),

    # Google APIs
    ("google-generativeai", "configure", "Gemini API 設定", "設定 Google Generative AI API 金鑰。", "https://ai.google.dev/api/python/google/generativeai#configure", "google.generativeai.configure"),
    ("google-generativeai", "GenerativeModel", "Gemini API 模型", "建立 Gemini 生成模型物件。", "https://ai.google.dev/api/python/google/generativeai/GenerativeModel", "google.generativeai.GenerativeModel"),
    ("google-generativeai", "generate_content", "Gemini API 生成", "呼叫模型產生文字或多模態內容。", "https://ai.google.dev/api/python/google/generativeai/GenerativeModel#generate_content", "GenerativeModel.generate_content"),
    ("google-generativeai", "start_chat", "Gemini API 對話", "建立可保留歷史的聊天物件。", "https://ai.google.dev/api/python/google/generativeai/GenerativeModel#start_chat", "GenerativeModel.start_chat"),

    ("gspread", "authorize", "gspread 授權", "使用憑證授權並建立 gspread client。", "https://docs.gspread.org/en/latest/api/auth.html", "gspread.authorize"),
    ("gspread", "open", "gspread 試算表", "依名稱開啟 Google Sheets 試算表。", "https://docs.gspread.org/en/latest/api/client.html#gspread.client.Client.open", "Client.open"),
    ("gspread", "open_by_key", "gspread 試算表", "依試算表 ID 開啟 Google Sheets。", "https://docs.gspread.org/en/latest/api/client.html#gspread.client.Client.open_by_key", "Client.open_by_key"),
    ("gspread", "worksheet", "gspread 工作表", "取得指定名稱的工作表。", "https://docs.gspread.org/en/latest/api/models/spreadsheet.html#gspread.spreadsheet.Spreadsheet.worksheet", "Spreadsheet.worksheet"),
    ("gspread", "get_all_records", "gspread 讀取", "把工作表資料讀成 dict list。", "https://docs.gspread.org/en/latest/api/models/worksheet.html#gspread.worksheet.Worksheet.get_all_records", "Worksheet.get_all_records"),
    ("gspread", "append_row", "gspread 寫入", "在工作表最後新增一列資料。", "https://docs.gspread.org/en/latest/api/models/worksheet.html#gspread.worksheet.Worksheet.append_row", "Worksheet.append_row"),
    ("gspread", "update", "gspread 寫入", "更新指定範圍的資料。", "https://docs.gspread.org/en/latest/api/models/worksheet.html#gspread.worksheet.Worksheet.update", "Worksheet.update"),

    ("google-cloud-storage", "Client", "Cloud Storage", "建立 Google Cloud Storage 客戶端。", "https://cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.client.Client", "google.cloud.storage.Client"),
    ("google-cloud-storage", "bucket", "Cloud Storage", "取得指定 bucket 物件。", "https://cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.client.Client#google_cloud_storage_client_Client_bucket", "Client.bucket"),
    ("google-cloud-storage", "blob", "Cloud Storage", "取得 bucket 中的 blob 物件。", "https://cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.bucket.Bucket#google_cloud_storage_bucket_Bucket_blob", "Bucket.blob"),
    ("google-cloud-storage", "upload_from_filename", "Cloud Storage", "上傳本機檔案到 Cloud Storage。", "https://cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.blob.Blob#google_cloud_storage_blob_Blob_upload_from_filename", "Blob.upload_from_filename"),
    ("google-cloud-storage", "download_to_filename", "Cloud Storage", "下載 Cloud Storage 檔案到本機。", "https://cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.blob.Blob#google_cloud_storage_blob_Blob_download_to_filename", "Blob.download_to_filename"),
    ("google-cloud-storage", "list_blobs", "Cloud Storage", "列出 bucket 中的檔案。", "https://cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.client.Client#google_cloud_storage_client_Client_list_blobs", "Client.list_blobs"),

    ("google-api-python-client", "build", "Google API Client", "建立 Google API 服務物件，例如 Drive、Sheets、Calendar。", "https://googleapis.github.io/google-api-python-client/docs/dyn/index.html", "googleapiclient.discovery.build"),
    ("google-api-python-client", "execute", "Google API Client", "執行建立好的 API request。", "https://googleapis.github.io/google-api-python-client/docs/", "HttpRequest.execute"),
    ("google-api-python-client", "files().list", "Google Drive API", "列出 Google Drive 檔案。", "https://developers.google.com/drive/api/reference/rest/v3/files/list", "drive.files().list"),
    ("google-api-python-client", "spreadsheets().values().get", "Google Sheets API", "讀取 Google Sheets 指定範圍資料。", "https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/get", "sheets.spreadsheets().values().get"),

    # PyQt6
    ("PyQt6", "QApplication", "PyQt6 基礎", "建立 GUI 應用程式物件。", "https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtwidgets/qapplication.html", "PyQt6.QtWidgets.QApplication"),
    ("PyQt6", "QWidget", "PyQt6 視窗", "基本視窗元件。", "https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtwidgets/qwidget.html", "PyQt6.QtWidgets.QWidget"),
    ("PyQt6", "QPushButton", "PyQt6 元件", "按鈕元件。", "https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtwidgets/qpushbutton.html", "PyQt6.QtWidgets.QPushButton"),
    ("PyQt6", "QLineEdit", "PyQt6 元件", "單行文字輸入框。", "https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtwidgets/qlineedit.html", "PyQt6.QtWidgets.QLineEdit"),
    ("PyQt6", "QVBoxLayout", "PyQt6 版面", "垂直排列元件的版面配置。", "https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtwidgets/qvboxlayout.html", "PyQt6.QtWidgets.QVBoxLayout"),
    ("PyQt6", "QMessageBox", "PyQt6 對話框", "顯示提示、警告、確認視窗。", "https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtwidgets/qmessagebox.html", "PyQt6.QtWidgets.QMessageBox"),
    ("PyQt6", "QTreeWidget", "PyQt6 樹狀清單", "建立樹狀資料顯示元件。", "https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtwidgets/qtreewidget.html", "PyQt6.QtWidgets.QTreeWidget"),
    ("PyQt6", "QTextEdit", "PyQt6 文字區", "多行文字顯示或編輯元件。", "https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtwidgets/qtextedit.html", "PyQt6.QtWidgets.QTextEdit"),

    # openpyxl
    ("openpyxl", "load_workbook", "openpyxl 讀取", "讀取既有 Excel 檔案。", "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html#openpyxl.reader.excel.load_workbook", "openpyxl.load_workbook"),
    ("openpyxl", "Workbook", "openpyxl 建立", "建立新的 Excel 活頁簿。", "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.workbook.workbook.html", "openpyxl.Workbook"),
    ("openpyxl", "cell", "openpyxl 儲存格", "讀寫指定儲存格資料。", "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.cell.cell.html", "Worksheet.cell"),
    ("openpyxl", "append", "openpyxl 寫入", "在工作表最後新增一列資料。", "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.worksheet.worksheet.html", "Worksheet.append"),
    ("openpyxl", "save", "openpyxl 儲存", "儲存 Excel 檔案。", "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.workbook.workbook.html", "Workbook.save"),
    ("openpyxl", "iter_rows", "openpyxl 讀取", "逐列讀取工作表資料。", "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.worksheet.worksheet.html", "Worksheet.iter_rows"),
    ("openpyxl", "Font", "openpyxl 樣式", "設定文字字型樣式。", "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.styles.fonts.html", "openpyxl.styles.Font"),
    ("openpyxl", "PatternFill", "openpyxl 樣式", "設定儲存格填滿顏色。", "https://openpyxl.readthedocs.io/en/stable/api/openpyxl.styles.fills.html", "openpyxl.styles.PatternFill"),

    # reportlab
    ("reportlab", "canvas.Canvas", "ReportLab PDF", "建立 PDF 畫布，適合直接繪製文字與圖形。", "https://docs.reportlab.com/reportlab/userguide/ch2_graphics/", "reportlab.pdfgen.canvas.Canvas"),
    ("reportlab", "drawString", "ReportLab PDF", "在 PDF 指定座標寫入文字。", "https://docs.reportlab.com/reportlab/userguide/ch2_graphics/", "Canvas.drawString"),
    ("reportlab", "save", "ReportLab PDF", "儲存並完成 PDF 檔案。", "https://docs.reportlab.com/reportlab/userguide/ch2_graphics/", "Canvas.save"),
    ("reportlab", "SimpleDocTemplate", "ReportLab Platypus", "建立較高階的 PDF 文件模板。", "https://docs.reportlab.com/reportlab/userguide/ch5_platypus/", "reportlab.platypus.SimpleDocTemplate"),
    ("reportlab", "Paragraph", "ReportLab Platypus", "建立可排版的文字段落。", "https://docs.reportlab.com/reportlab/userguide/ch6_paragraphs/", "reportlab.platypus.Paragraph"),
    ("reportlab", "Table", "ReportLab Platypus", "建立 PDF 表格。", "https://docs.reportlab.com/reportlab/userguide/ch7_tables/", "reportlab.platypus.Table"),

    # Celery
    ("celery", "Celery", "Celery App", "建立 Celery 應用程式物件。", "https://docs.celeryq.dev/en/stable/reference/celery.html", "celery.Celery"),
    ("celery", "task", "Celery 任務", "宣告 Celery 任務。", "https://docs.celeryq.dev/en/stable/userguide/tasks.html", "app.task"),
    ("celery", "shared_task", "Celery 任務", "宣告可在 Django 等專案共用的任務。", "https://docs.celeryq.dev/en/stable/reference/celery.html#celery.shared_task", "celery.shared_task"),
    ("celery", "delay", "Celery 執行", "非同步送出任務。", "https://docs.celeryq.dev/en/stable/userguide/calling.html", "task.delay"),
    ("celery", "apply_async", "Celery 執行", "用更多參數控制非同步任務執行。", "https://docs.celeryq.dev/en/stable/userguide/calling.html", "task.apply_async"),
    ("celery", "AsyncResult", "Celery 結果", "查詢非同步任務狀態與結果。", "https://docs.celeryq.dev/en/stable/reference/celery.result.html", "celery.result.AsyncResult"),

    # python-dotenv
    ("python-dotenv", "load_dotenv", "python-dotenv 載入", "讀取 .env 檔案並載入環境變數。", "https://saurabh-kumar.com/python-dotenv/reference/#load_dotenv", "dotenv.load_dotenv"),
    ("python-dotenv", "dotenv_values", "python-dotenv 讀取", "讀取 .env 檔案並回傳 dict，不直接改環境變數。", "https://saurabh-kumar.com/python-dotenv/reference/#dotenv_values", "dotenv.dotenv_values"),
    ("python-dotenv", "find_dotenv", "python-dotenv 尋找", "自動尋找 .env 檔案路徑。", "https://saurabh-kumar.com/python-dotenv/reference/#find_dotenv", "dotenv.find_dotenv"),
    ("python-dotenv", "set_key", "python-dotenv 寫入", "在 .env 檔案設定某個 key 的值。", "https://saurabh-kumar.com/python-dotenv/reference/#set_key", "dotenv.set_key"),
    ("python-dotenv", "get_key", "python-dotenv 讀取", "從 .env 檔案讀取指定 key 的值。", "https://saurabh-kumar.com/python-dotenv/reference/#get_key", "dotenv.get_key"),
]


def clean_text(text):
    if text is None:
        return ""

    return " ".join(text.strip().split())


def fetch_soup(url):
    headers = {
        "User-Agent": "Python Function Search Learning Project"
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


def get_item_id(dt_tag):
    if dt_tag is None:
        return ""

    return dt_tag.get("id", "")


def get_display_name(dt_tag, item_id):
    if dt_tag is None:
        return ""

    name_tag = dt_tag.select_one(".sig-name.descname")

    if name_tag:
        return clean_text(name_tag.get_text())

    if item_id:
        return item_id.split(".")[-1]

    return ""


def guess_package(item_id, default_package):
    if not item_id:
        return default_package

    parts = item_id.split(".")

    if len(parts) >= 2:
        return ".".join(parts[:-1])

    return default_package


def get_first_description(dl_tag):
    if dl_tag is None:
        return ""

    p = dl_tag.select_one("dd p")

    if p is None:
        return ""

    return clean_text(p.get_text())


def get_first_example(dl_tag):
    if dl_tag is None:
        return ""

    pre = dl_tag.select_one("dd pre")

    if pre is None:
        return ""

    return pre.get_text().strip()


def normalized_text(value):
    return value.strip().lower().replace("_", "-") if value else ""


def is_match(entry, keyword):
    keyword = keyword.strip().lower()

    if keyword == "":
        return True

    entry_package = entry.package.lower()
    entry_name = entry.name.lower()
    entry_anchor = entry.source_anchor.lower()

    # 支援 sklearn / scikit-learn、bs4 / beautifulsoup 等別名
    canonical = canonical_package_name(keyword).lower()

    return (
        entry_package.startswith(keyword)
        or entry_name.startswith(keyword)
        or entry_anchor.startswith(keyword)
        or entry_package.startswith(canonical)
        or entry_name.startswith(canonical)
        or entry_anchor.startswith(canonical)
        or keyword in entry_anchor
    )


def parse_python_doc_page(page_info, keyword):
    """
    解析 Python 官方 Sphinx 文件頁面。
    """

    url = page_info["url"]
    default_package = page_info["default_package"]
    category = page_info["category"]

    soup = fetch_soup(url)
    entries = []

    dl_tags = soup.select(
        "dl.py.function, dl.py.method, dl.py.class, dl.py.data, dl.py.attribute"
    )

    for dl in dl_tags:
        dt = dl.find("dt")

        item_id = get_item_id(dt)
        name = get_display_name(dt, item_id)
        package = guess_package(item_id, default_package)

        if not name:
            continue

        entry = FunctionEnter(
            name=name,
            package=package,
            category=category,
            description_zh=get_first_description(dl),
            description_en="",
            example=get_first_example(dl),
            source=url,
            source_anchor=item_id
        )

        if is_match(entry, keyword):
            entries.append(entry)

    return entries


def get_builtin_fallback_entries(keyword):
    entries = []

    for package, name, category, description_zh, source_anchor in BUILTIN_FALLBACK_DATA:
        entry = FunctionEnter(
            name=name,
            package=package,
            category=category,
            description_zh=description_zh,
            description_en="",
            example="",
            source=urljoin(PYTHON_BASE_URL, "stdtypes.html"),
            source_anchor=source_anchor
        )

        if is_match(entry, keyword):
            entries.append(entry)

    return entries


def get_third_party_fallback_entries(keyword):
    entries = []

    for package, name, category, description_zh, source, source_anchor in THIRD_PARTY_FALLBACK_DATA:
        entry = FunctionEnter(
            name=name,
            package=package,
            category=category,
            description_zh=description_zh,
            description_en="",
            example="",
            source=source,
            source_anchor=source_anchor
        )

        if is_match(entry, keyword):
            entries.append(entry)

    return entries


def should_try_package_discovery(keyword, existing_entries):
    """
    判斷是否需要用 PyPI 找官方文件入口。

    情境：
    1. 沒有任何 fallback / Python 文件結果 → 可以試 PyPI
    2. 使用者輸入很像套件名，例如包含 - 或 _
    3. 使用者輸入是固定官方來源表裡的套件
    """

    key = keyword.strip().lower()

    if key == "":
        return False

    if not existing_entries:
        return True

    if "-" in key or "_" in key:
        return True

    if key in OFFICIAL_DOC_SOURCES or key in PACKAGE_ALIASES:
        return True

    return False


def get_official_source_entry(keyword):
    """
    依照內建官方來源表或 PyPI，建立一筆「官方文件入口」資料。

    如果是內建表找得到，就不用連 PyPI。
    如果內建表找不到，就去 PyPI JSON API 找 documentation / homepage。
    """

    raw_key = keyword.strip()
    key = raw_key.lower()
    canonical = canonical_package_name(raw_key)
    canonical_key = canonical.lower()

    # 1. 內建官方來源表
    if key in OFFICIAL_DOC_SOURCES:
        doc_url = OFFICIAL_DOC_SOURCES[key]
        package = canonical
        return FunctionEnter(
            name="官方文件入口",
            package=package,
            category="第三方套件官方來源",
            description_zh=f"這是 {package} 的官方文件入口。若需要完整 API，請從來源網址進入官方文件查詢。",
            description_en="",
            example="",
            source=doc_url,
            source_anchor=f"{package}.official_docs"
        )

    if canonical_key in OFFICIAL_DOC_SOURCES:
        doc_url = OFFICIAL_DOC_SOURCES[canonical_key]
        package = canonical
        return FunctionEnter(
            name="官方文件入口",
            package=package,
            category="第三方套件官方來源",
            description_zh=f"這是 {package} 的官方文件入口。若需要完整 API，請從來源網址進入官方文件查詢。",
            description_en="",
            example="",
            source=doc_url,
            source_anchor=f"{package}.official_docs"
        )

    # 2. PyPI 自動探索
    try:
        info = discover_package_from_pypi(raw_key)
    except Exception as e:
        print("PyPI 查詢失敗：", e)
        return None

    if info is None:
        return None

    package = info["pypi_name"]
    summary = info["summary"]
    doc_url = info["doc_url"]
    pypi_url = info["pypi_url"]

    description = f"從 PyPI 找到 {package} 的套件資料。"
    if summary:
        description += f"\nPyPI 摘要：{summary}"
    description += f"\n若來源網址不是完整文件，請再參考 PyPI 專案頁：{pypi_url}"

    return FunctionEnter(
        name="PyPI 官方來源",
        package=package,
        category="PyPI 套件來源",
        description_zh=description,
        description_en=summary,
        example="",
        source=doc_url,
        source_anchor=f"{package}.pypi_source"
    )


def pick_python_pages(keyword):
    """
    根據關鍵字挑選 Python 官方文件頁面。
    """

    key = keyword.strip().lower()

    third_party_keys = set(OFFICIAL_DOC_SOURCES.keys()) | set(PACKAGE_ALIASES.keys())

    # 第三方套件不爬 Python 標準函式庫頁面
    if key in third_party_keys:
        return []

    if key in {"list", "dict", "str", "set", "tuple"}:
        return [page for page in PYTHON_DOC_PAGES if page["url"].endswith("stdtypes.html")]

    if key in {"math", "sqrt", "sin", "cos", "tan", "floor", "ceil", "log"}:
        return [page for page in PYTHON_DOC_PAGES if page["url"].endswith("math.html")]

    if key in {"statistics", "mean", "median", "mode", "stdev", "variance"}:
        return [page for page in PYTHON_DOC_PAGES if page["url"].endswith("statistics.html")]

    if key in {"collections", "counter", "deque", "defaultdict", "namedtuple"}:
        return [page for page in PYTHON_DOC_PAGES if page["url"].endswith("collections.html")]

    return PYTHON_DOC_PAGES


def dedupe_entries(entries):
    seen = set()
    result = []

    for entry in entries:
        key = (entry.package.lower(), entry.name.lower())

        if key not in seen:
            seen.add(key)
            result.append(entry)

    return result


def search_from_docs(keyword):
    """
    app.py 會呼叫這個函式。

    回傳 FunctionEnter list。
    """

    entries = []

    # Python 內建型別 fallback
    entries.extend(get_builtin_fallback_entries(keyword))

    # 第三方套件 fallback
    entries.extend(get_third_party_fallback_entries(keyword))

    # Python 官方繁中說明文件
    for page_info in pick_python_pages(keyword):
        try:
            entries.extend(parse_python_doc_page(page_info, keyword))
            time.sleep(0.4)
        except Exception as e:
            print(f"爬取失敗：{page_info['url']}")
            print("錯誤原因：", e)

    # 官方文件入口 / PyPI 來源
    if should_try_package_discovery(keyword, entries):
        source_entry = get_official_source_entry(keyword)
        if source_entry is not None:
            entries.append(source_entry)

    return dedupe_entries(entries)
