import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QInputDialog, QLineEdit, QLabel,
    QComboBox, QFormLayout, QDialog, QVBoxLayout, QWidget,
    QHBoxLayout
)
from PyQt5.QtGui import QIcon, QFont, QPixmap
from PyQt5.QtCore import Qt
import psycopg2


class DatabaseManager:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname="mosaic_db",
            user="postgres",
            password="toor",
            host="localhost",
            port=5432
        )
        self.cur = self.conn.cursor()

    def get_materials(self):
        try:
            self.cur.execute("""
                SELECT m.material_id, m.name, mt.name, 
                       m.price_per_unit, m.quantity_in_stock, m.min_quantity, 
                       m.quantity_per_package, m.unit_of_measurement
                FROM materials m
                JOIN material_types mt ON m.material_type_id = mt.material_type_id
            """)
            return self.cur.fetchall()
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(None, "Ошибка БД", f"Не удалось загрузить материалы: {str(e)}")
            return []

    def get_material_types(self):
        try:
            self.cur.execute("SELECT material_type_id, name FROM material_types")
            return self.cur.fetchall()
        except Exception as e:
            return []

    def add_material(self, name, type_id, price, quantity, min_qty, package_qty, unit):
        try:
            self.cur.execute("""
                INSERT INTO materials (
                    name, material_type_id, price_per_unit, quantity_in_stock,
                    min_quantity, quantity_per_package, unit_of_measurement
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, type_id, price, quantity, min_qty, package_qty, unit))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

    def update_material(self, mid, name, type_id, price, quantity, min_qty, package_qty, unit):
        try:
            self.cur.execute("""
                UPDATE materials SET 
                    name=%s, material_type_id=%s, price_per_unit=%s,
                    quantity_in_stock=%s, min_quantity=%s,
                    quantity_per_package=%s, unit_of_measurement=%s
                WHERE material_id=%s
            """, (name, type_id, price, quantity, min_qty, package_qty, unit, mid))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

    def delete_material(self, mid):
        try:
            self.cur.execute("DELETE FROM materials WHERE material_id=%s", (mid,))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

    def get_suppliers_by_material(self, mid):
        try:
            self.cur.execute("""
                SELECT s.name
                FROM suppliers s
                JOIN material_suppliers ms ON s.supplier_id = ms.supplier_id
                WHERE ms.material_id = %s
            """, (mid,))
            return [row[0] for row in self.cur.fetchall()]
        except Exception as e:
            return []

    def calculate_product_count(self, product_type_id, material_id, raw_amount, param1, param2):
        try:
            # Получаем коэффициент типа продукции
            self.cur.execute("SELECT coefficient FROM product_types WHERE product_type_id = %s", (product_type_id,))
            coeff_row = self.cur.fetchone()
            if not coeff_row:
                return -1
            coefficient = coeff_row[0]

            # Получаем цену материала
            self.cur.execute("SELECT price_per_unit FROM materials WHERE material_id = %s", (material_id,))
            price_row = self.cur.fetchone()
            if not price_row:
                return -1
            price = price_row[0]

            # Рассчитываем необходимое сырьё
            required_raw = param1 * param2 * coefficient
            adjusted_raw = required_raw * 1.1  # добавляем 10% потерь
            products = int(raw_amount // adjusted_raw)

            return products

        except Exception as e:
            return -1


class MaterialDialog(QDialog):
    def __init__(self, db, material=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить материал" if not material else "Редактировать материал")
        self.setWindowIcon(QIcon('icon.ico'))
        self.setStyleSheet("background-color: #FFFFFF; font-family: 'Comic Sans MS';")
        self.db = db
        self.material = material
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        self.name_input = QLineEdit()
        self.price_input = QLineEdit()
        self.qty_input = QLineEdit()
        self.min_qty_input = QLineEdit()
        self.pkg_qty_input = QLineEdit()
        self.unit_input = QLineEdit()
        self.type_combo = QComboBox()

        types = self.db.get_material_types()
        for tid, tname in types:
            self.type_combo.addItem(tname, tid)

        if self.material:
            self.name_input.setText(self.material[1])
            idx = self.type_combo.findData(self.material[2])
            self.type_combo.setCurrentIndex(idx)
            self.price_input.setText(str(self.material[3]))
            self.qty_input.setText(str(self.material[4]))
            self.min_qty_input.setText(str(self.material[5]))
            self.pkg_qty_input.setText(str(self.material[6]))
            self.unit_input.setText(self.material[7])

        layout.addRow("Наименование:", self.name_input)
        layout.addRow("Тип материала:", self.type_combo)
        layout.addRow("Цена единицы:", self.price_input)
        layout.addRow("Количество на складе:", self.qty_input)
        layout.addRow("Минимальное количество:", self.min_qty_input)
        layout.addRow("Количество в упаковке:", self.pkg_qty_input)
        layout.addRow("Единица измерения:", self.unit_input)

        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet("background-color: #546F94; color: white;")
        save_btn.clicked.connect(self.save_material)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def save_material(self):
        try:
            name = self.name_input.text()
            type_id = self.type_combo.currentData()
            price = float(self.price_input.text())
            quantity = float(self.qty_input.text())
            min_quantity = float(self.min_qty_input.text())
            package_quantity = float(self.pkg_qty_input.text())
            unit = self.unit_input.text()

            if not name or not unit:
                raise ValueError("Пожалуйста, заполните все поля")

            if self.material:
                self.db.update_material(
                    self.material[0], name, type_id, price, quantity,
                    min_quantity, package_quantity, unit
                )
            else:
                self.db.add_material(
                    name, type_id, price, quantity,
                    min_quantity, package_quantity, unit
                )
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить материал: {str(e)}")


class ProductCalcDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Расчёт количества продукции")
        self.setWindowIcon(QIcon('icon.ico'))
        self.setStyleSheet("background-color: #FFFFFF; font-family: 'Comic Sans MS';")
        self.db = db
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        self.product_type_combo = QComboBox()
        self.material_combo = QComboBox()
        self.raw_input = QLineEdit()
        self.param1_input = QLineEdit()
        self.param2_input = QLineEdit()
        self.result_label = QLabel("Количество продукции: ?")

        # Загружаем типы продукции
        self.db.cur.execute("SELECT product_type_id, name FROM product_types")
        self.product_types = self.db.cur.fetchall()
        for pid, pname in self.product_types:
            self.product_type_combo.addItem(pname, pid)

        # Загружаем материалы
        materials = self.db.get_materials()
        for mat in materials:
            self.material_combo.addItem(mat[1], mat[0])

        layout.addRow("Тип продукции:", self.product_type_combo)
        layout.addRow("Материал:", self.material_combo)
        layout.addRow("Используемое сырьё:", self.raw_input)
        layout.addRow("Параметр 1:", self.param1_input)
        layout.addRow("Параметр 2:", self.param2_input)
        layout.addRow(self.result_label)

        calc_btn = QPushButton("Рассчитать")
        calc_btn.setStyleSheet("background-color: #546F94; color: white;")
        calc_btn.clicked.connect(self.calculate)
        layout.addWidget(calc_btn)

        self.setLayout(layout)

    def calculate(self):
        try:
            product_type_id = self.product_type_combo.currentData()
            material_id = self.material_combo.currentData()
            raw_amount = float(self.raw_input.text())
            param1 = float(self.param1_input.text())
            param2 = float(self.param2_input.text())

            count = self.db.calculate_product_count(product_type_id, material_id, raw_amount, param1, param2)
            if count == -1:
                self.result_label.setText("Ошибка: некорректные данные.")
            else:
                self.result_label.setText(f"Количество продукции: {count}")
        except Exception as e:
            self.result_label.setText(f"Ошибка: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Производственная компания — «Мозаика»")
        self.setWindowIcon(QIcon('icon.ico'))

        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
                font-family: 'Comic Sans MS';
            }
            QPushButton {
                background-color: #546F94;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #6A8AAE;
            }
            QTableWidget {
                gridline-color: #BBD9B2;
                selection-background-color: #546F94;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #546F94;
                color: white;
                padding: 6px;
            }
        """)

        self.db = DatabaseManager()
        self.init_ui()
        self.load_materials()

    def init_ui(self):
        main_layout = QVBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap("mosaic.png").scaledToWidth(100))
        logo.setAlignment(Qt.AlignCenter)

        title = QLabel("Производственная компания — «Мозаика»")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Comic Sans MS", 14, QFont.Bold))

        self.materials_table = QTableWidget()
        self.materials_table.setColumnCount(8)
        self.materials_table.setHorizontalHeaderLabels([
            "ID", "Наименование", "Тип", "Цена", "Остаток", "Минимум", "Упаковка", "Ед."
        ])
        self.materials_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.materials_table.verticalHeader().setVisible(False)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Добавить")
        edit_btn = QPushButton("✏️ Редактировать")
        del_btn = QPushButton("❌ Удалить")
        supp_btn = QPushButton("🔍 Поставщики")
        prod_btn = QPushButton("🧮 Производство")

        add_btn.clicked.connect(self.add_material)
        edit_btn.clicked.connect(self.edit_material)
        del_btn.clicked.connect(self.delete_material)
        supp_btn.clicked.connect(self.show_suppliers)
        prod_btn.clicked.connect(self.open_production)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addWidget(supp_btn)
        btn_layout.addWidget(prod_btn)

        main_layout.addWidget(logo)
        main_layout.addWidget(title)
        main_layout.addWidget(self.materials_table)
        main_layout.addLayout(btn_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def load_materials(self):
        materials = self.db.get_materials()
        self.materials_table.setRowCount(len(materials))
        for row, mat in enumerate(materials):
            for col, val in enumerate(mat):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.materials_table.setItem(row, col, item)
        self.materials_table.resizeColumnsToContents()

    def add_material(self):
        dialog = MaterialDialog(self.db)
        if dialog.exec_():
            self.load_materials()

    def edit_material(self):
        selected = self.materials_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите материал для редактирования")
            return
        mid = int(selected[0].text())
        materials = self.db.get_materials()
        material = next((m for m in materials if m[0] == mid), None)
        if material:
            dialog = MaterialDialog(self.db, material)
            if dialog.exec_():
                self.load_materials()

    def delete_material(self):
        selected = self.materials_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите материал для удаления")
            return
        mid = int(selected[0].text())
        reply = QMessageBox.question(
            self, "Подтверждение", "Вы уверены, что хотите удалить этот материал?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_material(mid)
            self.load_materials()

    def show_suppliers(self):
        selected = self.materials_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите материал")
            return
        mid = int(selected[0].text())
        suppliers = self.db.get_suppliers_by_material(mid)
        if not suppliers:
            QMessageBox.information(self, "Информация", "Нет поставщиков для этого материала")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Поставщики")
        dialog.resize(500, 300)
        layout = QVBoxLayout()
        table = QTableWidget()
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(["Поставщик"])
        table.setRowCount(len(suppliers))
        for i, name in enumerate(suppliers):
            table.setItem(i, 0, QTableWidgetItem(name))
        layout.addWidget(table)
        dialog.setLayout(layout)
        dialog.exec_()

    def open_production(self):
        dialog = ProductCalcDialog(self.db)
        dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Comic Sans MS", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())