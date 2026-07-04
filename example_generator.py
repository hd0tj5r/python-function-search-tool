# example_generator.py
# -*- coding: utf-8 -*-

"""
範例產生層：安全手寫範例

這個檔案只放「已檢查過的手寫範例」。
如果找不到手寫範例，會回傳 None，讓 app.py 可以改用 AI 產生範例。
"""


MANUAL_EXAMPLES = {
    # Python list
    "list.append": """numbers = [1, 2, 3]
numbers.append(4)

print(numbers)
# 輸出: [1, 2, 3, 4]""",

    "list.sort": """scores = [80, 65, 90, 75]
scores.sort()

print(scores)
# 輸出: [65, 75, 80, 90]""",

    # NumPy
    "numpy.array": """import numpy as np

data = np.array([1, 2, 3])

print(data)
# 輸出: [1 2 3]""",

    "numpy.mean": """import numpy as np

scores = np.array([80, 90, 70])

print(np.mean(scores))
# 輸出: 80.0""",

    # pandas
    "pandas.DataFrame": """import pandas as pd

df = pd.DataFrame({
    "name": ["Amy", "Bob"],
    "score": [90, 80]
})

print(df)
# 輸出一個表格型資料""",

    "pandas.read_csv": """import pandas as pd

df = pd.read_csv("data.csv")

print(df.head())
# 顯示前 5 筆資料""",

    # seaborn
    "seaborn.scatterplot": """import seaborn as sns
import matplotlib.pyplot as plt

tips = sns.load_dataset("tips")
sns.scatterplot(data=tips, x="total_bill", y="tip")

plt.show()
# 顯示 total_bill 和 tip 的散佈圖""",

    # TensorFlow
    "tensorflow.constant": """import tensorflow as tf

x = tf.constant([1, 2, 3])

print(x)
# 建立 TensorFlow 張量""",

    # requests
    "requests.get": """import requests

response = requests.get("https://example.com")

print(response.status_code)
print(response.text[:100])
# 取得網頁內容""",

    # BeautifulSoup
    "beautifulsoup4.BeautifulSoup": """from bs4 import BeautifulSoup

html = "<h1>Hello</h1>"
soup = BeautifulSoup(html, "html.parser")

print(soup.h1.text)
# 輸出: Hello""",

    # Selenium
    "selenium.webdriver.Chrome": """from selenium import webdriver

driver = webdriver.Chrome()
driver.get("https://example.com")

print(driver.title)

driver.quit()
# 開啟瀏覽器後關閉""",

    # Flask
    "flask.Flask": """from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello Flask"

app.run(debug=True)
# 建立最簡單的 Flask 網站""",

    # FastAPI
    "fastapi.FastAPI": """from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello FastAPI"}

# 執行方式:
# uvicorn main:app --reload""",

    # google-generativeai
    "google-generativeai.GenerativeModel": """import google.generativeai as genai

genai.configure(api_key="你的_API_KEY")

model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("請用一句話介紹 Python")

print(response.text)""",

    # gspread
    "gspread.open_by_key": """import gspread

gc = gspread.service_account(filename="service_account.json")
sheet = gc.open_by_key("試算表_ID").sheet1

print(sheet.get_all_records())
# 讀取 Google Sheets 資料""",

    # openpyxl
    "openpyxl.Workbook": """from openpyxl import Workbook

wb = Workbook()
ws = wb.active

ws.append(["name", "score"])
ws.append(["Amy", 90])

wb.save("scores.xlsx")
# 建立 Excel 檔案""",

    # PyQt6
    "PyQt6.QApplication": """import sys
from PyQt6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle("Hello PyQt6")
window.show()

sys.exit(app.exec())""",

    # python-dotenv
    "python-dotenv.load_dotenv": """from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("API_KEY")

print(api_key)
# 從 .env 讀取環境變數"""
}


def get_manual_example(name, package):
    """
    如果有手寫範例，回傳範例。
    如果沒有，回傳 None。
    """

    key = f"{package}.{name}"

    return MANUAL_EXAMPLES.get(key)


def make_waiting_example(name, package, description):
    """
    沒有手寫範例、也還沒按 AI 產生時，顯示用的提示文字。
    不建議直接把這種提示文字存進資料庫。
    """

    return f"""# 尚未產生範例：{package}.{name}
# 說明：{description}

# 你可以點「AI 產生範例」讓 Gemini 產生一個初學者範例。
"""
