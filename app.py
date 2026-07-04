# app.py
# -*- coding: utf-8 -*-

"""
Python 函式查詢工具：PyPI 整合優化版

流程：
1. 使用者搜尋
2. 先查本機 functions.db
3. 若關鍵字尚未補資料，才呼叫 crawler.py
4. crawler.py 會補 Python / 第三方套件 fallback / PyPI 官方來源
5. 補到的資料同步存進 functions.db
6. 前端以「套件 → 函式」樹狀顯示
7. 點開函式時，如果沒有範例，就用 example_generator.py 補安全範例
"""

import sys

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QPlainTextEdit,
    QMessageBox, QLabel, QComboBox, QCheckBox, QTabWidget, QSplitter, QScrollArea
)
from PyQt6.QtCore import Qt

from database import FunctionDatabase, FunctionEnter
from crawler import search_from_docs
from example_generator import get_manual_example, make_waiting_example
from ai_example_generator import generate_example_with_ai, get_default_model, save_api_key_to_env


class FunctionSearchApp(QWidget):
    def __init__(self):
        super().__init__()

        self.db = FunctionDatabase()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Python 函式查詢工具")
        self.resize(1150, 900)
        self.setMinimumSize(760, 620)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "輸入套件或函式，例如：list、numpy、seaborn、requests、fastapi、python-dotenv"
        )

        search_button = QPushButton("搜尋 / 補資料")
        search_button.clicked.connect(lambda: self.search_function(force_crawl=False))

        force_button = QPushButton("強制重新補資料")
        force_button.clicked.connect(lambda: self.search_function(force_crawl=True))

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        search_layout.addWidget(force_button)

        self.status_label = QLabel(
            "提示：先查本機資料庫；關鍵字尚未補資料時，才補官方文件來源、常用函式或 PyPI 資料。"
        )

        # ---------- AI 設定區 ----------
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItem("Gemini", "gemini")
        self.ai_provider_combo.addItem("GPT / OpenAI", "openai")
        self.ai_provider_combo.addItem("Claude", "claude")
        self.ai_provider_combo.currentIndexChanged.connect(self.update_ai_model_default)

        self.ai_model_input = QLineEdit()
        self.ai_model_input.setText(get_default_model("gemini"))
        self.ai_model_input.setPlaceholderText("模型名稱，例如 gemini-2.5-flash、gpt-5.5、claude-sonnet-4-5")

        self.ai_api_key_input = QLineEdit()
        self.ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key_input.setPlaceholderText("在這裡輸入目前選擇服務的 API Key；不輸入則讀 .env")

        self.save_api_key_checkbox = QCheckBox("將這次輸入的 API Key 存到 .env")
        self.save_api_key_checkbox.setToolTip("會以純文字寫入 .env。請不要把 .env 上傳到 GitHub 或分享給別人。")

        ai_layout = QHBoxLayout()
        ai_layout.addWidget(QLabel("AI 服務:"))
        ai_layout.addWidget(self.ai_provider_combo)
        ai_layout.addWidget(QLabel("模型:"))
        ai_layout.addWidget(self.ai_model_input)
        ai_layout.addWidget(QLabel("API Key:"))
        ai_layout.addWidget(self.ai_api_key_input)
        ai_layout.addWidget(self.save_api_key_checkbox)

        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["套件 / 函式"])
        self.result_tree.itemClicked.connect(self.show_detail)
        self.result_tree.setMinimumHeight(220)

        # ---------- 詳細內容分頁 ----------
        self.detail_tabs = QTabWidget()
        self.detail_tabs.setMinimumHeight(320)

        self.description_view = QTextEdit()
        self.description_view.setReadOnly(True)

        self.example_view = QPlainTextEdit()
        self.example_view.setReadOnly(True)
        self.example_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.example_view.setMinimumHeight(260)

        self.source_view = QTextEdit()
        self.source_view.setReadOnly(True)

        self.detail_tabs.addTab(self.description_view, "說明")
        self.detail_tabs.addTab(self.example_view, "範例程式碼")
        self.detail_tabs.addTab(self.source_view, "來源")

        delete_button = QPushButton("刪除這筆資料")
        delete_button.clicked.connect(self.delete_current)

        ai_example_button = QPushButton("AI 產生 / 更新範例")
        ai_example_button.clicked.connect(self.generate_ai_example_for_current)

        copy_example_button = QPushButton("複製範例程式碼")
        copy_example_button.clicked.connect(self.copy_example_to_clipboard)

        self.new_name = QLineEdit()
        self.new_package = QLineEdit()
        self.new_category = QLineEdit()
        self.new_description = QTextEdit()
        self.new_description.setPlaceholderText("中文說明")
        self.new_example = QTextEdit()
        self.new_example.setPlaceholderText("範例程式碼")

        form_layout = QFormLayout()
        form_layout.addRow("函式名稱:", self.new_name)
        form_layout.addRow("套件 / 型別:", self.new_package)
        form_layout.addRow("分類:", self.new_category)
        form_layout.addRow("中文說明:", self.new_description)
        form_layout.addRow("範例程式碼:", self.new_example)

        add_button = QPushButton("新增 / 更新這筆資料")
        add_button.clicked.connect(self.add_new_function)

        # 上下可拖拉區塊：
        # 上方結果清單、下方詳細內容分頁
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.result_tree)
        splitter.addWidget(self.detail_tabs)
        splitter.setSizes([320, 520])

        action_layout = QHBoxLayout()
        action_layout.addWidget(delete_button)
        action_layout.addWidget(ai_example_button)
        action_layout.addWidget(copy_example_button)

        # 內容主區塊
        # 放進 QScrollArea，視窗高度不夠時可以上下滾動。
        content_widget = QWidget()
        content_widget.setMinimumHeight(1080)

        content_layout = QVBoxLayout(content_widget)
        content_layout.addLayout(search_layout)
        content_layout.addWidget(self.status_label)
        content_layout.addLayout(ai_layout)
        content_layout.addWidget(splitter)
        content_layout.addLayout(action_layout)
        content_layout.addLayout(form_layout)
        content_layout.addWidget(add_button)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content_widget)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        window_layout = QVBoxLayout()
        window_layout.addWidget(scroll_area)

        self.setLayout(window_layout)

    def clear_detail_tabs(self):
        """
        清空說明、範例、來源三個分頁。
        """

        self.description_view.clear()
        self.example_view.clear()
        self.source_view.clear()
        self.detail_tabs.setCurrentIndex(0)

    def copy_example_to_clipboard(self):
        """
        複製目前範例程式碼。
        """

        code = self.example_view.toPlainText().strip()

        if not code:
            QMessageBox.information(self, "提醒", "目前沒有範例程式碼可以複製")
            return

        QApplication.clipboard().setText(code)
        self.status_label.setText("已複製範例程式碼到剪貼簿。")

    def update_ai_model_default(self):
        """
        切換 Gemini / GPT / Claude 時，自動帶入預設模型名稱。
        你仍然可以手動修改模型欄位。
        """

        provider = self.ai_provider_combo.currentData()
        self.ai_model_input.setText(get_default_model(provider))

    def get_ai_settings(self):
        """
        取得前端目前選擇的 AI 設定。
        """

        provider = self.ai_provider_combo.currentData()
        model_name = self.ai_model_input.text().strip()
        api_key = self.ai_api_key_input.text().strip()

        return provider, model_name, api_key

    def search_function(self, force_crawl=False):
        keyword = self.search_input.text().strip()

        self.status_label.setText("正在查詢本機資料庫...")
        QApplication.processEvents()

        results = self.db.search(keyword)

        should_crawl = False

        if keyword != "":
            if force_crawl:
                should_crawl = True
            elif not self.db.was_keyword_fetched(keyword):
                should_crawl = True
            elif len(results) == 0:
                should_crawl = True

        if should_crawl:
            self.status_label.setText("正在補官方文件、常用函式與 PyPI 套件來源...")
            QApplication.processEvents()

            entries = search_from_docs(keyword)

            for entry in entries:
                self.db.add_function(entry)

            self.db.record_keyword_fetch(keyword, len(entries))

            results = self.db.search(keyword)

            if entries:
                self.status_label.setText(
                    f"已補資料 {len(entries)} 筆，並同步存進 functions.db。"
                )
            else:
                self.status_label.setText(
                    f"找不到 {keyword} 的資料；PyPI 或目前支援清單也沒有找到。"
                )
        else:
            self.status_label.setText(f"從本機資料庫讀取，共 {len(results)} 筆。")

        self.display_results(results)

    def display_results(self, results):
        self.result_tree.clear()
        self.clear_detail_tabs()

        if hasattr(self, "current_selected_id"):
            del self.current_selected_id

        if hasattr(self, "current_selected_row"):
            del self.current_selected_row

        if not results:
            item = QTreeWidgetItem(["查無資料"])
            item.setData(0, Qt.ItemDataRole.UserRole, None)
            self.result_tree.addTopLevelItem(item)
            return

        package_dict = {}

        for row in results:
            package = row["package"] if row["package"] else "未分類"
            package_dict.setdefault(package, []).append(row)

        for package, rows in package_dict.items():
            package_item = QTreeWidgetItem([package])
            package_item.setData(0, Qt.ItemDataRole.UserRole, None)

            for row in rows:
                function_item = QTreeWidgetItem([row["name"]])
                function_item.setData(0, Qt.ItemDataRole.UserRole, dict(row))
                package_item.addChild(function_item)

            self.result_tree.addTopLevelItem(package_item)

        self.result_tree.expandAll()

    def show_detail(self, item):
        row = item.data(0, Qt.ItemDataRole.UserRole)

        if row is None:
            self.clear_detail_tabs()

            if hasattr(self, "current_selected_id"):
                del self.current_selected_id

            if hasattr(self, "current_selected_row"):
                del self.current_selected_row

            return

        entry_id = row["id"]
        name = row["name"]
        package = row["package"]
        category = row["category"] or ""
        description_zh = row["description_zh"] or ""
        description_en = row["description_en"] or ""
        example = row["example"] or ""
        source = row["source"] or ""
        source_anchor = row["source_anchor"] or ""

        self.current_selected_id = entry_id
        self.current_selected_row = row

        if example.strip() == "":
            manual_example = get_manual_example(name=name, package=package)

            if manual_example:
                example = manual_example
                self.db.update_example(entry_id, example)
                row["example"] = example
            else:
                example = make_waiting_example(
                    name=name,
                    package=package,
                    description=description_zh or description_en
                )

        description_text = (
            f"套件 / 型別: {package}\n"
            f"函式: {name}\n"
            f"分類: {category}\n\n"
            f"中文說明:\n{description_zh}\n"
        )

        if description_en:
            description_text += f"\n英文說明:\n{description_en}\n"

        source_text = (
            f"來源網址:\n{source}\n\n"
            f"錨點:\n{source_anchor}"
        )

        self.description_view.setText(description_text)
        self.example_view.setPlainText(example)
        self.source_view.setText(source_text)

        # 點選函式時預設顯示範例，因為範例通常最長、最需要空間。
        self.detail_tabs.setCurrentIndex(1)

    def generate_ai_example_for_current(self):
        """
        對目前選取的函式，用 AI 產生範例並存回資料庫。
        """

        if not hasattr(self, "current_selected_row"):
            QMessageBox.warning(self, "提醒", "請先從清單點選一筆函式")
            return

        row = self.current_selected_row

        entry_id = row["id"]
        name = row["name"]
        package = row["package"]
        category = row["category"] or ""
        description_zh = row["description_zh"] or ""
        description_en = row["description_en"] or ""
        source_anchor = row["source_anchor"] or ""

        reply = QMessageBox.question(
            self,
            "AI 產生範例",
            f"要用 AI 產生 / 更新 {package}.{name} 的範例嗎？\n\n"
            "產生後會寫入 functions.db，會覆蓋這筆資料目前的範例。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.status_label.setText(f"正在用 AI 產生 {package}.{name} 的範例...")
        QApplication.processEvents()

        provider, model_name, api_key = self.get_ai_settings()

        if api_key and self.save_api_key_checkbox.isChecked():
            ok, save_message = save_api_key_to_env(provider, api_key)
            if ok:
                self.status_label.setText(save_message)
            else:
                QMessageBox.warning(self, "API Key 未儲存", save_message)

        result = generate_example_with_ai(
            name=name,
            package=package,
            category=category,
            description_zh=description_zh,
            description_en=description_en,
            source_anchor=source_anchor,
            provider=provider,
            api_key=api_key,
            model_name=model_name
        )

        if not result.ok:
            QMessageBox.warning(self, "AI 產生失敗", result.message)
            self.status_label.setText(result.message)
            return

        self.db.update_example(entry_id, result.code)

        # 更新目前記憶體中的 row，讓畫面立即刷新
        self.current_selected_row["example"] = result.code

        self.status_label.setText("AI 範例已產生，並存回 functions.db。")

        # 重新顯示詳細內容
        class FakeItem:
            def __init__(self, data):
                self._data = data

            def data(self, column, role):
                return self._data

        self.show_detail(FakeItem(self.current_selected_row))

        QMessageBox.information(self, "完成", "AI 範例已產生並存回資料庫。")

    def delete_current(self):
        if not hasattr(self, "current_selected_id"):
            QMessageBox.warning(self, "提醒", "請先從清單點選一筆要刪除的資料")
            return

        reply = QMessageBox.question(
            self,
            "確認刪除",
            "確定要刪除這筆資料嗎？此動作無法復原。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_by_id(self.current_selected_id)
            del self.current_selected_id
            self.clear_detail_tabs()
            self.search_function(force_crawl=False)
            QMessageBox.information(self, "完成", "已刪除")

    def add_new_function(self):
        name = self.new_name.text().strip()
        package = self.new_package.text().strip()
        category = self.new_category.text().strip()
        description_zh = self.new_description.toPlainText().strip()
        example = self.new_example.toPlainText().strip()

        if name == "":
            QMessageBox.warning(self, "提醒", "函式名稱不能是空的")
            return

        if package == "":
            QMessageBox.warning(self, "提醒", "套件 / 型別不能是空的，例如 list、numpy、pandas")
            return

        entry = FunctionEnter(
            name=name,
            package=package,
            category=category,
            description_zh=description_zh,
            description_en="",
            example=example,
            source="manual",
            source_anchor=f"{package}.{name}"
        )

        self.db.add_function(entry)

        self.new_name.clear()
        self.new_package.clear()
        self.new_category.clear()
        self.new_description.clear()
        self.new_example.clear()

        QMessageBox.information(self, "完成", f"已新增或更新：{package}.{name}")

        self.search_input.setText(package)
        self.search_function(force_crawl=False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FunctionSearchApp()
    window.show()
    sys.exit(app.exec())
