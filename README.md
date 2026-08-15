# Python 函式查詢工具：PyPI + 多 AI 範例產生版
![程式函式範例生成工具](程式函式範例生成工具.png)
## 這版新增

- API Key 可以直接在前端介面輸入
- 可以切換 AI 服務：
  - Gemini
  - GPT / OpenAI
  - Claude
- 可以在前端修改模型名稱
- 可選擇是否將 API Key 存進 `.env`
- 按「AI 產生 / 更新範例」後，會把產生的範例存回 `functions.db`

## 影片
https://youtu.be/Yx0LM-I0MUw

## 安裝

```bash
pip install -r requirements.txt
```

## 執行

```bash
python app.py
```

## 前端 AI 設定

畫面上會看到：

```text
AI 服務：Gemini / GPT / OpenAI / Claude
模型：可自行輸入
API Key：前端輸入
將這次輸入的 API Key 存到 .env
```

預設模型：

```text
Gemini: gemini-2.5-flash
GPT / OpenAI: gpt-5.5
Claude: claude-sonnet-4-5
```

如果你的帳號沒有某個模型權限，可以直接在模型欄位改成你有權限的模型。

## API Key

你可以每次在前端輸入 API Key。

也可以建立 `.env`：

```env
GEMINI_API_KEY=你的_Gemini_API_Key
OPENAI_API_KEY=你的_OpenAI_API_Key
ANTHROPIC_API_KEY=你的_Claude_API_Key
```

注意：`.env` 是純文字，請不要上傳 GitHub，也不要分享給別人。

## 使用流程

1. 搜尋函式，例如 `requests`
2. 點選左邊的函式，例如 `get`
3. 選 AI 服務
4. 輸入 API Key
5. 按「AI 產生 / 更新範例」
6. 範例會存回 `functions.db`

## 安全限制

AI 產生範例後會做簡單檢查，阻止：

- os.remove
- shutil.rmtree
- subprocess
- eval
- exec
- while True
- rm -rf
- DROP TABLE
- DELETE FROM


## UI 優化版新增

這版把原本擠在一起的詳細內容改成：

```text
可拖拉 QSplitter
├─ 上方：套件 / 函式清單
└─ 下方：分頁
    ├─ 說明
    ├─ 範例程式碼
    └─ 來源
```

新增：

- 結果清單與詳細內容可以上下拖拉調整大小
- 範例程式碼獨立分頁，避免和說明擠在一起
- 來源網址獨立分頁
- 新增「複製範例程式碼」按鈕


## 捲動版新增

這版在整個主畫面外層加入 `QScrollArea`：

```text
QScrollArea
└─ 主內容
   ├─ 搜尋列
   ├─ AI 設定列
   ├─ 可拖拉 QSplitter
   ├─ 操作按鈕
   └─ 手動新增表單
```

當視窗高度不夠時，可以用滑鼠滾輪上下捲動，不會再切掉下方欄位。
