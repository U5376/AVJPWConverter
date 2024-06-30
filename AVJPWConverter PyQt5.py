import os
import threading
import logging
import time
import warnings
from PIL import Image
import pillow_avif
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QObject
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QDesktopServices
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLineEdit, QTextEdit,
    QFileDialog, QVBoxLayout, QWidget, QLabel, QComboBox, QSpinBox,
    QHBoxLayout, QFormLayout, QGroupBox, QTableWidget, QTableWidgetItem,
    QDialog, QHeaderView)

warnings.filterwarnings("ignore", category=DeprecationWarning)

# 自定义日志处理类
class LogEmitter(QObject):
    log_message = pyqtSignal(str)

class TextHandler(logging.Handler):
    def __init__(self, emitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record):
        msg = self.format(record)
        self.emitter.log_message.emit(msg)

log = logging.getLogger(__name__)

class DraggableLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]
        self.setText(";".join(paths))  # 使用";"分隔路径
        log.info(f"拖放的文件: {';'.join(paths)}")  # 记录日志
        print(f"拖放的文件: {';'.join(paths)}")  # 调试日志

# 全局变量用来控制转换过程
conversion_paused = threading.Event()

def run_conversion(input_files, output_dir, img_format, quality, compress, pause_event, log, progress_label):
    log.info("开始转换过程：")
    files = []

    if len(input_files) == 1 and os.path.isdir(input_files[0]):  # 输入是目录
        for filename in os.listdir(input_files[0]):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".avif")):
                files.append(os.path.join(input_files[0], filename))
    else:  # 输入是单个文件或多个文件
        files = input_files

    total_files = len(files)
    failed_count = 0
    completed_count = 0

    for file in files:
        pause_event.wait()  # 检查是否暂停

        max_try = 3  # 最大重试次数
        try_count = 0  # 重试计数器

        while try_count < max_try:
            try:
                log.info(f"{os.path.basename(file)} 正在转换...")

                image = Image.open(file)

                # 生成新的文件名，其扩展名改为所需格式
                new_file_name = os.path.splitext(os.path.basename(file))[0] + '.' + img_format
                new_file_path = os.path.join(output_dir, new_file_name)
                
                # 检查输出路径是否存在，不存在则创建
                os.makedirs(output_dir, exist_ok=True)                

                # 变换图像并保存
                if img_format in ["jpg", "jpeg", "webp", "avif"]:
                    image.save(new_file_path, quality=quality)
                elif img_format == "png":
                    image.save(new_file_path, compress_level=compress)

                log.info(f"{os.path.basename(file)} 成功转换为 {img_format} 格式！")
                completed_count += 1
                break  # 转换成功，跳出循环
            except Exception as e:
                log.error(f"转换 {file} 失败。错误原因: {e}")
                log.info(f"正在重试转换 {os.path.basename(file)}")
                try_count += 1
                time.sleep(1)  # 等待一秒后重试

        if try_count == max_try:
            log.error(f"转换 {file} 失败次数超过最大重试次数，跳过转换")
            failed_count += 1

        # 更新进度信息标签
        progress_label.setText(f"转换失败: {failed_count} 已完成/总数: {completed_count}/{total_files}")

    log.info("所有图像转换已完成！")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AVJPWConverter PyQt5")
        self.setGeometry(100, 100, 600, 620)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout()

        input_group = QGroupBox("输入选项")
        input_layout = QFormLayout()
        self.input_button = QPushButton("选择输入文件")
        self.input_button.clicked.connect(self.select_input_files)
        self.input_button.setFixedWidth(90)  # 固定宽度
        self.input_dir_button = QPushButton("选择输入文件夹")
        self.input_dir_button.clicked.connect(self.select_input_dir)
        self.input_dir_button.setFixedWidth(100)  # 固定宽度
        self.input_line = DraggableLineEdit()
        self.input_line.setPlaceholderText("拖放文件到此处")
        # 使用 QHBoxLayout 创建按钮布局
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.input_button)
        button_layout.addWidget(self.input_dir_button)
        input_layout.addRow(button_layout)
        # 调整 QLabel 和输入框的对齐方式
        input_path_layout = QHBoxLayout()
        input_path_label = QLabel("输入路径:")
        input_path_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        input_path_layout.addWidget(input_path_label)
        input_path_layout.addWidget(self.input_line)
        input_layout.addRow(input_path_layout)
        input_group.setLayout(input_layout)

        output_group = QGroupBox("输出选项")
        output_layout = QFormLayout()
        self.output_button = QPushButton("选择输出路径")
        self.output_button.clicked.connect(self.select_output_dir)
        self.output_button.setFixedWidth(90)  # 固定宽度
        self.output_line = DraggableLineEdit()
        self.output_line.setPlaceholderText("拖放文件夹到此处")
        # 使用 QHBoxLayout 创建按钮布局并添加到 FormLayout
        output_button_layout = QHBoxLayout()
        output_button_layout.addWidget(self.output_button)
        output_button_layout.addWidget(QLabel())  # 添加一个空的 QLabel 占位符，确保布局对齐
        output_layout.addRow(output_button_layout)
        # 调整 QLabel 和输入框的对齐方式
        output_path_layout = QHBoxLayout()
        output_path_label = QLabel("输出路径:")
        output_path_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        output_path_layout.addWidget(output_path_label)
        output_path_layout.addWidget(self.output_line)
        output_layout.addRow(output_path_layout)
        output_group.setLayout(output_layout)

        format_group = QGroupBox("格式选项")
        format_layout = QFormLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(['jpg', 'png', 'webp', 'avif'])
        self.format_combo.setCurrentText('avif')  # 设置默认格式为AVIF
        self.format_combo.currentTextChanged.connect(self.update_quality_label)
        self.quality_label = QLabel("AVIF 质量 (1-63，默认值为 63):")
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 63)
        self.quality_spin.setValue(63)  # 设置默认质量为63
        format_layout.addRow(QLabel("图片格式:"), self.format_combo)
        format_layout.addRow(self.quality_label, self.quality_spin)
        format_group.setLayout(format_layout)
        self.format_combo.setFixedWidth(50)  # 设置下拉框的固定宽度
        self.quality_spin.setFixedWidth(50)   # 设置数值调节框的固定宽度

        control_group = QGroupBox("控制选项")
        control_layout = QHBoxLayout()
        self.convert_button = QPushButton("开始转换")
        self.convert_button.clicked.connect(self.convert_images)
        self.convert_button.setFixedWidth(100)  # 固定宽度
        self.pause_button = QPushButton("暂停/继续")
        self.pause_button.clicked.connect(self.pause_conversion)
        self.pause_button.setFixedWidth(100)  # 固定宽度
        self.clear_log_button = QPushButton("清空日志")
        self.clear_log_button.clicked.connect(self.clear_log)
        self.clear_log_button.setFixedWidth(100)  # 固定宽度
        self.show_list_button = QPushButton("显示文件列表")
        self.show_list_button.clicked.connect(self.show_file_list)
        self.show_list_button.setFixedWidth(100)  # 固定宽度
        # 创建打开输出文件夹按钮
        self.open_output_button = QPushButton("打开输出文件夹")
        self.open_output_button.clicked.connect(self.open_output_folder)
        self.open_output_button.setFixedWidth(120)  # 固定宽度        
        control_layout.addWidget(self.convert_button)
        control_layout.addWidget(self.pause_button)
        control_layout.addWidget(self.show_list_button)
        control_layout.addWidget(self.open_output_button)
        control_layout.addWidget(self.clear_log_button)
        control_group.setLayout(control_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #f0f0f0;")

        progress_layout = QHBoxLayout()
        progress_label_title = QLabel("日志输出:")
        self.progress_label = QLabel("转换失败: 0 已完成/总数: 0/0")
        self.progress_label.setAlignment(Qt.AlignRight)
        progress_layout.addWidget(progress_label_title)
        progress_layout.addWidget(self.progress_label)

        main_layout.addWidget(input_group)
        main_layout.addWidget(output_group)
        main_layout.addWidget(format_group)
        main_layout.addWidget(control_group)
        main_layout.addLayout(progress_layout)
        main_layout.addWidget(self.log_output)

        self.central_widget.setLayout(main_layout)

        self.setAcceptDrops(True)

        self.log = logging.getLogger()
        self.log.setLevel(logging.INFO)

        self.log_emitter = LogEmitter()
        self.log_emitter.log_message.connect(self.log_output.append)

        handler = TextHandler(self.log_emitter)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
        self.log.handlers = [handler]

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]
        drop_pos = event.pos()
        if self.input_line.geometry().contains(drop_pos):
            self.input_line.setText(";".join(paths))
            print(f"输入路径设置为: {paths}")  # 调试日志
        elif self.output_line.geometry().contains(drop_pos):
            self.output_line.setText(paths[0])
            print(f"输出路径设置为: {paths[0]}")  # 调试日志

    def select_input_files(self):
        input_files, _ = QFileDialog.getOpenFileNames(self, "选择输入文件")
        self.input_line.setText(";".join(input_files))
        self.log.info(f"选择的输入文件是: {input_files}")
        print(f"选择的输入文件是: {input_files}")  # 调试日志

    def select_input_dir(self):
        input_dir = QFileDialog.getExistingDirectory(self, "选择输入文件夹")
        if input_dir and not input_dir.endswith(os.path.sep):  # 检查路径末尾是否有斜杠
            input_dir += os.path.sep
        self.input_line.setText(input_dir)
        self.log.info(f"选择的输入文件夹是: {input_dir}")
        print(f"选择的输入文件夹是: {input_dir}")  # 调试日志

    def select_output_dir(self):
        output_dir = QFileDialog.getExistingDirectory(self, "选择输出路径")
        self.output_line.setText(output_dir)
        self.log.info(f"选择的输出目录是: {output_dir}")
        print(f"选择的输出目录是: {output_dir}")  # 调试日志

    def open_output_folder(self):
        output_dir = self.output_line.text()
        if output_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(output_dir))
        else:
            self.log.info("未选择输出路径")

    def update_quality_label(self, text):
        if (text == 'jpg'):
            self.quality_label.setText('JPEG 质量 (1-100，默认值为 90):')
            self.quality_spin.setRange(1, 100)
            self.quality_spin.setValue(90)
        elif (text == 'png'):
            self.quality_label.setText('PNG 压缩级别 (0-9，默认值为 6):')
            self.quality_spin.setRange(0, 9)
            self.quality_spin.setValue(6)
        elif (text == 'webp'):
            self.quality_label.setText('WebP 质量 (0-100，默认值为 80):')
            self.quality_spin.setRange(0, 100)
            self.quality_spin.setValue(80)
        elif (text == 'avif'):
            self.quality_label.setText('AVIF 质量 (1-63，默认值为 63):')
            self.quality_spin.setRange(1, 63)
            self.quality_spin.setValue(63)

    def convert_images(self):
        if (self.input_line.text() == ''):
            self.log_output.append('请选择输入的文件夹')
        else:
            input_files = self.input_line.text().split(";")
            output_dir = self.output_line.text()
            if output_dir == '':
                if input_files and os.path.isdir(input_files[0]):
                    output_dir = os.path.join(input_files[0], 'processed')
                    os.makedirs(output_dir, exist_ok=True)
                    self.log.info(f"输出路径为空，将在输入路径下创建文件夹processed")

            img_format = self.format_combo.currentText()
            quality = self.quality_spin.value()
            compress = self.quality_spin.value()
            if (img_format == 'png'):
                compress = min(compress, 9)  # 限制压缩级别最大为9
            elif (img_format == 'avif'):
                compress = min(compress, 63)  # 限制压缩级别最大为63

            conversion_paused.set()
            convert_thread = threading.Thread(target=run_conversion, args=(input_files, output_dir, img_format, quality, compress, conversion_paused, self.log, self.progress_label))
            convert_thread.start()
            self.pause_button.setText('暂停')  # 更新按钮文本

    def clear_log(self):
        self.log_output.clear()

    def pause_conversion(self):
        if conversion_paused.is_set():
            conversion_paused.clear()
            self.pause_button.setText('继续')
            self.log.info('转换已暂停')
        else:
            conversion_paused.set()
            self.pause_button.setText('暂停')
            self.log.info('转换已继续')

    def show_file_list(self):
        input_files = self.input_line.text().split(";")
        if not input_files:
            self.log.info('未选择输入文件或文件夹')
            return

        files = []
        if len(input_files) == 1 and os.path.isdir(input_files[0]):  # 输入是目录
            for filename in os.listdir(input_files[0]):
                if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".avif")):
                    files.append(os.path.join(input_files[0], filename))
        else:  # 输入是单个文件或多个文件
            files = input_files

        if not files:
            self.log.info('未找到可转换的文件')
            return

        file_list_dialog = QDialog()
        file_list_dialog.setWindowTitle('文件列表')
        file_list_dialog.setGeometry(200, 200, 700, 500)

        layout = QVBoxLayout()

        table = QTableWidget()
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(['文件路径'])
        table.setRowCount(len(files))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 自动调整列宽

        for i, file in enumerate(files):
            item = QTableWidgetItem(file)
            table.setItem(i, 0, item)

        layout.addWidget(table)

        file_list_dialog.setLayout(layout)
        file_list_dialog.exec_()

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
