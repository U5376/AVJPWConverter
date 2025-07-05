import sys
import os
import threading
import logging
import time
import pillow_avif
import warnings
from PIL import Image, ImageEnhance
from send2trash import send2trash
from PySide6.QtCore import Qt, Signal, QUrl, QObject
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLineEdit, QTextEdit,
    QFileDialog, QVBoxLayout, QWidget, QLabel, QComboBox, QSpinBox,
    QHBoxLayout, QFormLayout, QGroupBox, QTableWidget, QTableWidgetItem,
    QDialog, QHeaderView, QCheckBox, QGridLayout, QDoubleSpinBox)
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import psutil
import multiprocessing
import configparser

warnings.filterwarnings("ignore", category=DeprecationWarning)

# 自定义日志处理类
class LogEmitter(QObject):
    log_message = Signal(str)

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
        current_text = self.text()
        existing_paths = current_text.split(";") if current_text else []
        combined_paths = existing_paths + paths
        unique_paths = list(dict.fromkeys(combined_paths))  # 保留顺序并去重
        self.setText(";".join(unique_paths))
        log.info(f"拖放的文件: {';'.join(paths)}")  # 记录日志

# 全局变量用来控制转换过程
conversion_paused = threading.Event()
conversion_paused.set()  # 初始为“运行”状态
conversion_stopped = False  # 新增全局停止标志

def process_file(file, output_dir, img_format, quality, compress, height, width,
                delete_original, adjust_height, adjust_width, sharpness, 
                preserve_metadata, log, method=None, speed=None):
    logs = []
    try:
        # 使用 pathlib 处理路径
        file_path = Path(file)
        image = Image.open(str(file_path))
        file_name = file_path.name

        # 如果图像是 RGBA 模式，并且目标格式是 jpg/jpeg，则转换为 RGB 模式
        if img_format in ["jpg", "jpeg"] and image.mode == 'RGBA':
            image = image.convert('RGB')
            logs.append(f"图像 {file_name} 的 Alpha 通道已被移除，转换为 RGB 模式")

        # 如果需要调整高度或宽度，则调整图像大小，保持纵横比，不放大较小的图片
        if (adjust_height and image.height > height) or (adjust_width and image.width > width):
            aspect_ratio = image.width / image.height
            if adjust_height and adjust_width:
                # 取高宽最低的那个数值为主
                if height < width / aspect_ratio:
                    new_height = height
                    new_width = int(height * aspect_ratio)
                else:
                    new_width = width
                    new_height = int(width / aspect_ratio)
            elif adjust_height:
                new_height = height
                new_width = int(height * aspect_ratio)
            elif adjust_width:
                new_width = width
                new_height = int(width / aspect_ratio)
            image = image.resize((new_width, new_height), Image.LANCZOS)

        # 添加锐化处理：当锐化因子不为默认值 1.0 时，进行图像锐化
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(sharpness)

        # 根据是否指定了输出目录，决定文件的输出路径
        if output_dir:  # 如果指定了输出路径
            output_dir_path = Path(output_dir)
            new_file_path = output_dir_path / file_name
            new_file_name = new_file_path.with_suffix(f'.{img_format}').name
            new_file_path = output_dir_path / new_file_name
        else:  # 如果未指定输出路径，使用文件的原目录
            new_file_name = file_path.with_suffix(f'.{img_format}').name
            file_output_dir = file_path.parent  # 使用文件的原目录作为输出目录
            new_file_path = file_output_dir / new_file_name

        # 检查输出路径是否存在，不存在则创建
        new_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 变换图像并保存
        if img_format in ["jpg", "jpeg", "webp", "avif"]:
            if img_format == "webp":
                # 自定义method为6 最优最慢1-6 原值默认4
                image.save(str(new_file_path), quality=quality, method=method if method is not None else 6)
            elif img_format == "avif":
                # 自定义speed为4 最优最慢0-10 原值默认6
                image.save(str(new_file_path), quality=quality, speed=speed if speed is not None else 4)
            else:
                image.save(str(new_file_path), quality=quality)
        elif img_format == "png":
            image.save(str(new_file_path), compress_level=compress)

        # 是否保留元数据
        if preserve_metadata:
            original_stat = file_path.stat()
            os.utime(str(new_file_path), (original_stat.st_atime, original_stat.st_mtime))

        logs.append(f"{file_path.name:<50} 成功转为{img_format}")

        # 如果选择了删除原文件，则删除
        if delete_original:
            absolute_path = str(file_path.resolve())
            send2trash(absolute_path)

        return True, logs
    except Exception as e:
        logs.append(f"转换 {file} 失败。错误原因: {e}")
        return False, logs

def run_conversion(input_files, output_dir, img_format, quality, compress, height, width,
                   delete_original, adjust_height, adjust_width, sharpness, pause_event,
                   stop_event, log, progress_label, preserve_metadata, on_finished,
                   thread_count=None, method=None, speed=None):
    global conversion_stopped
    conversion_stopped = False

    def set_low_priority():
        try:
            p = psutil.Process(os.getpid())
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except Exception as e:
            log.warning(f"无法设置低优先级: {e}")

    try:
        set_low_priority()
        log.info("开始转换过程：")
        if sharpness != 1.0:
            log.info(f"锐化因子：{sharpness}")

        files = []
        for input_path in input_files:
            p = Path(input_path)
            if p.is_dir():
                files += [str(f) for f in p.rglob('*') if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp', '.avif']]
            elif p.is_file() and p.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp', '.avif']:
                files.append(str(p))

        if output_dir:
            log.info(f"输出路径指定为: {output_dir}")
        else:
            if len(input_files) == 1:
                p = Path(input_files[0])
                if p.is_dir():
                    log.info(f"输出路径为空，使用原文件夹路径: {input_files[0]}")
                else:
                    log.info(f"输出路径为空，使用原文件路径: {str(p.parent)}")
            else:
                log.info(f"输出路径为空，输出在原文件路径.公共路径: {os.path.commonpath(input_files)}")

        total_files = len(files)
        failed_count = 0
        completed_count = 0

        if thread_count is not None:
            max_workers = thread_count
        else:
            max_workers = multiprocessing.cpu_count()
        max_workers = max(1, max_workers)
        log.info(f"使用线程数: {max_workers}")

        progress = [None] * total_files

        def file_task(idx, file):
            # 检查暂停/停止
            while not pause_event.is_set():
                if stop_event.is_set():
                    return 'stopped', idx, file, []
                time.sleep(0.1)
            if stop_event.is_set():
                return 'stopped', idx, file, []
            try_count = 0
            max_try = 3
            while try_count < max_try:
                if stop_event.is_set():
                    return 'stopped', idx, file, []
                try:
                    ok, logs = process_file(file, output_dir, img_format, quality, compress, height, width,
                        delete_original, adjust_height, adjust_width, sharpness, preserve_metadata, log,
                        method=method, speed=speed)
                    return ok, idx, file, logs
                except Exception as e:
                    logs = [f"转换 {file} 失败。错误原因: {e}"]
                    try_count += 1
                    time.sleep(1)
            return False, idx, file, logs

        with ThreadPoolExecutor(max_workers=max_workers) as executor:

            # --- 顺序输出日志 ---
            results = executor.map(lambda args: file_task(*args), enumerate(files))
            for idx, (ok, idx2, file, logs) in enumerate(results):
                # 顺序输出日志
                for msg in logs:
                    log.info(msg)
                progress[idx] = ok
                completed_count = sum(1 for v in progress if v is True)
                failed_count = sum(1 for v in progress if v is False)
                progress_label.setText(f"转换失败: {failed_count} 已完成/总数: {completed_count}/{total_files}")
                if ok == 'stopped':
                    log.info("转换被用户终止")
                    break

        log.info("所有图像转换已完成！")
    except Exception as e:
        log.error(f"转换过程发生错误: {str(e)}")
    finally:
        on_finished()
        log.info("转换流程结束")

class MainWindow(QMainWindow):
    clear_input_signal = Signal()

    def __init__(self):
        super().__init__()
        # 设置全局字体
        font = QFont("宋体", 9)
        QApplication.instance().setFont(font)

        self.convert_thread = None  # 添加线程引用

        self.setWindowTitle("AVJPWConverter PySide6")
        self.setGeometry(100, 100, 515, 620)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout()

        # 工具函数减少重复
        def make_btn(text, slot, width):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            btn.setFixedWidth(width)
            return btn

        def make_label(text, align=Qt.AlignRight | Qt.AlignVCenter):
            label = QLabel(text)
            label.setAlignment(align)
            return label

        def make_spinbox(minv, maxv, val, width=50, tooltip=None):
            sb = QSpinBox()
            sb.setRange(minv, maxv)
            sb.setValue(val)
            sb.setFixedWidth(width)
            if tooltip:
                sb.setToolTip(tooltip)
            return sb

        # 输入选项
        input_group = QGroupBox("输入选项")
        input_layout = QFormLayout()
        self.input_button = make_btn("选择输入文件", self.select_input_files, 90)
        self.input_dir_button = make_btn("选择输入文件夹", self.select_input_dir, 100)
        self.show_list_button = make_btn("显示文件列表", self.show_file_list, 90)
        self.input_line = DraggableLineEdit()
        self.input_line.setPlaceholderText("拖放文件到此处")
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.input_button)
        button_layout.addWidget(self.input_dir_button)
        button_layout.addStretch()
        button_layout.addWidget(self.show_list_button)  # 靠右
        input_layout.addRow(button_layout)
        input_path_layout = QHBoxLayout()
        input_path_layout.addWidget(make_label("输入路径:"))
        input_path_layout.addWidget(self.input_line)
        input_layout.addRow(input_path_layout)
        input_group.setLayout(input_layout)

        # 输出选项
        output_group = QGroupBox("输出选项")
        output_layout = QFormLayout()
        self.output_button = make_btn("选择输出路径", self.select_output_dir, 90)
        self.open_output_button = make_btn("打开输出文件夹", self.open_output_folder, 100)
        self.output_line = DraggableLineEdit()
        self.output_line.setPlaceholderText("拖放文件夹到此处")
        self.cpu_combo = QComboBox()
        cpu_count = multiprocessing.cpu_count()
        self.cpu_combo.addItems([str(i) for i in range(1, cpu_count+1)])
        self.cpu_combo.setCurrentText(str(cpu_count))
        self.cpu_combo.setFixedWidth(30)
        cpu_label = make_label("线程")
        output_top_layout = QHBoxLayout()
        output_top_layout.addWidget(self.output_button)
        output_top_layout.addWidget(self.open_output_button)  # 放在选择输出路径按钮后
        output_top_layout.addStretch()
        output_top_layout.addWidget(cpu_label)
        output_top_layout.addWidget(self.cpu_combo)
        output_layout.addRow(output_top_layout)
        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(make_label("输出路径:"))
        output_path_layout.addWidget(self.output_line)
        output_layout.addRow(output_path_layout)
        output_group.setLayout(output_layout)

        # 格式选项
        format_group = QGroupBox("格式选项")
        format_layout = QGridLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(['jpg', 'png', 'webp', 'avif'])
        self.format_combo.setCurrentText('avif')
        self.format_combo.currentTextChanged.connect(self.update_quality_label)
        self.format_combo.setFixedWidth(50)
        self.quality_label = QLabel("AVIF质量")
        self.quality_spin = make_spinbox(1, 63, 63, tooltip="AVIF 质量 (1-63，默认值为 63)")

        # 新增 method/speed 下拉框
        self.method_label = QLabel("method")
        self.method_combo = QComboBox()
        self.method_combo.addItems([str(i) for i in range(0, 7)])
        self.method_combo.setCurrentText("6")
        self.method_combo.setFixedWidth(40)
        self.method_combo.setToolTip("1-6 默认6 越大压缩越慢越优 原值默认4")
        self.method_label.setVisible(False)
        self.method_combo.setVisible(False)

        self.speed_label = QLabel("speed")
        self.speed_combo = QComboBox()
        self.speed_combo.addItems([str(i) for i in range(0, 11)])
        self.speed_combo.setCurrentText("4")
        self.speed_combo.setFixedWidth(40)
        self.speed_combo.setToolTip("0-10 默认4 0最慢最优 原值默认6 推介2-4")
        self.speed_label.setVisible(False)
        self.speed_combo.setVisible(False)

        # 删除原文件、保留元数据、method/speed下拉框
        self.delete_original_checkbox = QCheckBox("转换后删除原文件")
        self.delete_original_checkbox.setChecked(False)
        self.preserve_metadata_checkbox = QCheckBox("保留修改时间")
        self.preserve_metadata_checkbox.setChecked(True)
        combined_layout = QHBoxLayout()
        combined_layout.addWidget(self.delete_original_checkbox)
        combined_layout.addSpacing(8)
        combined_layout.addWidget(self.preserve_metadata_checkbox)
        # 新增：method/speed 下拉框放到复选框右侧
        combined_layout.addSpacing(32)
        combined_layout.addWidget(self.method_label)
        combined_layout.addWidget(self.method_combo)
        combined_layout.addWidget(self.speed_label)
        combined_layout.addWidget(self.speed_combo)
        format_layout.addLayout(combined_layout, 0, 1, 1, 3, Qt.AlignLeft)
        format_group.setLayout(format_layout)
        # 保存 combined_layout 到 self 以便后续访问
        self.combined_layout = combined_layout
        self.format_group = format_group

        # 高宽选项
        dimension_layout = QHBoxLayout()
        self.height_checkbox = QCheckBox("图片高度")
        self.height_checkbox.setChecked(True)
        self.height_checkbox.stateChanged.connect(self.toggle_height_spin)
        self.height_spin = make_spinbox(1, 10000, 768, tooltip="按高宽最低值保持纵横比缩放")
        self.width_checkbox = QCheckBox("图片宽度")
        self.width_checkbox.setChecked(False)
        self.width_checkbox.stateChanged.connect(self.toggle_width_spin)
        self.width_spin = make_spinbox(1, 10000, 1500)
        self.width_spin.setEnabled(False)
        dimension_layout.addWidget(self.height_checkbox)
        dimension_layout.addWidget(self.height_spin)
        dimension_layout.addWidget(self.width_checkbox)
        dimension_layout.addWidget(self.width_spin)
        # 锐化相关下拉框
        sharpness_label = QLabel("锐化")
        self.sharpness_spin = QDoubleSpinBox()
        self.sharpness_spin.setRange(-2.0, 3.0)
        self.sharpness_spin.setSingleStep(0.1)
        self.sharpness_spin.setValue(1.0)
        self.sharpness_spin.setToolTip("1.0不处理,范围:负2-3(1.7-8有效减轻avif格式彩色CG眼睛线条糊化)")
        dimension_layout.addWidget(sharpness_label)
        dimension_layout.addWidget(self.sharpness_spin)
        # 质量下拉框
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(self.quality_label)
        quality_layout.addWidget(self.quality_spin)
        # 图片格式下拉框
        format_combo_layout = QHBoxLayout()
        format_combo_layout.addWidget(QLabel("图片格式"))
        format_combo_layout.addWidget(self.format_combo)
        # 三个元件位置
        format_layout.addLayout(format_combo_layout, 0, 0, 1, 1, Qt.AlignLeft)
        format_layout.addLayout(quality_layout, 1, 0, 1, 1, Qt.AlignLeft)
        format_layout.addLayout(dimension_layout, 1, 1, 1, 1, Qt.AlignLeft)

        # 控制选项
        control_group = QGroupBox("控制选项")
        control_layout = QHBoxLayout()
        control_layout.setSpacing(0)
        control_layout.setSpacing(10)
        control_layout.setAlignment(Qt.AlignLeft)
        self.convert_button = make_btn("开始转换", self.convert_images, 70)
        self.pause_button = make_btn("暂停/继续", self.pause_conversion, 70)
        self.stop_button = make_btn("停止", self.stop_conversion, 70)
        self.stop_event = threading.Event()
        self.clear_input_signal.connect(self.clear_input_line)
        self.save_settings_button = make_btn("保存设置", self.save_settings, 70)
        self.reset_settings_button = make_btn("重置设置", self.reset_settings, 70)
        self.clear_log_button = make_btn("清空日志", self.clear_log, 70)
        for btn in [self.convert_button, self.pause_button, self.stop_button,
                    self.save_settings_button, self.reset_settings_button, self.clear_log_button]:
            control_layout.addWidget(btn)
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

        # 主布局
        for w in [input_group, output_group, format_group, control_group]:
            main_layout.addWidget(w)
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

        # 修改配置文件路径获取方式，兼容 nuitka 单文件
        self.config_path = str(Path(sys.argv[0]).parent / "config.ini")
        self.config = configparser.ConfigParser()
        self.load_settings()  # 启动时加载设置
        self.update_quality_label(self.format_combo.currentText())  # 初始化时同步显示

    def toggle_method_speed(self, text):
        """根据格式显示/隐藏 method/speed 下拉框"""
        self.method_label.setVisible(False)
        self.method_combo.setVisible(False)
        self.speed_label.setVisible(False)
        self.speed_combo.setVisible(False)
        if text == 'webp':
            self.method_label.setVisible(True)
            self.method_combo.setVisible(True)
        elif text == 'avif':
            self.speed_label.setVisible(True)
            self.speed_combo.setVisible(True)

        # 强制刷新布局（防止 AttributeError）
        if hasattr(self, "combined_layout"):
            self.combined_layout.update()
        if hasattr(self, "format_group"):
            self.format_group.adjustSize()

    def toggle_height_spin(self, state):
        # 直接使用复选框的isChecked方法
        self.height_spin.setEnabled(self.height_checkbox.isChecked())
        if not self.height_checkbox.isChecked():
            self.height_spin.setValue(768)

    def toggle_width_spin(self, state):
        self.width_spin.setEnabled(self.width_checkbox.isChecked())
        if not self.width_checkbox.isChecked():
            self.width_spin.setValue(1500)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]
        drop_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if self.input_line.geometry().contains(drop_pos):
            self.input_line.setText(";".join(paths))
        elif self.output_line.geometry().contains(drop_pos):
            self.output_line.setText(paths[0])

    def select_input_files(self):
        input_files, _ = QFileDialog.getOpenFileNames(self, "选择输入文件")
        self.input_line.setText(";".join(input_files))
        self.log.info(f"选择的输入文件是: {input_files}")

    def select_input_dir(self):
        input_dir = QFileDialog.getExistingDirectory(self, "选择输入文件夹")
        if input_dir:
            # 用 Path 保证末尾有分隔符
            input_dir = str(Path(input_dir))
        self.input_line.setText(input_dir)
        self.log.info(f"选择的输入文件夹是: {input_dir}")

    def select_output_dir(self):
        output_dir = QFileDialog.getExistingDirectory(self, "选择输出路径")
        self.output_line.setText(str(Path(output_dir)) if output_dir else "")
        self.log.info(f"选择的输出目录是: {output_dir}")

    def open_output_folder(self):
        output_dir = self.output_line.text()
        input_files = self.input_line.text().split(";")  # 获取输入文件路径列表

        if not output_dir:
            input_paths = [Path(f) for f in input_files if f]
            if len(input_paths) > 1:
                try:
                    output_dir = str(os.path.commonpath([str(p) for p in input_paths]))
                except Exception:
                    output_dir = str(input_paths[0].parent) if input_paths else ""
            elif len(input_paths) == 1:
                if input_paths[0].is_dir():
                    output_dir = str(input_paths[0])
                else:
                    output_dir = str(input_paths[0].parent)
        if output_dir and Path(output_dir).is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(output_dir))
        else:
            print("未选择有效的输出路径或路径不存在")

    def update_quality_label(self, text):
        if text == 'jpg':
            self.quality_label.setText('JPEG质量')
            self.quality_spin.setRange(1, 100)
            self.quality_spin.setValue(90)
            self.quality_spin.setToolTip("JPEG 质量范围：1-100，默认90")
        elif text == 'png':
            self.quality_label.setText('PNG压缩')
            self.quality_spin.setRange(0, 9)
            self.quality_spin.setValue(6)
            self.quality_spin.setToolTip("PNG 压缩级别 (0-9，默认值为 6")
        elif text == 'webp':
            self.quality_label.setText('WebP质量')
            self.quality_spin.setRange(0, 100)
            self.quality_spin.setValue(80)
            self.quality_spin.setToolTip("WebP 质量 (0-100，默认值为 80)")
        elif text == 'avif':
            self.quality_label.setText('AVIF质量')
            self.quality_spin.setRange(1, 63)
            self.quality_spin.setValue(63)
            self.quality_spin.setToolTip("AVIF 质量 (1-63，默认值为 63)")
        self.toggle_method_speed(text)

    def convert_images(self):
        if self.input_line.text() == '':
            self.log_output.append('请选择输入文件')
        else:
            # 优化：用 Path 处理输入输出路径
            input_files = [str(Path(f)) for f in self.input_line.text().split(";") if f]
            output_dir = self.output_line.text()
            if output_dir:
                output_dir = str(Path(output_dir))
            else:
                output_dir = None  # 让 run_conversion 使用默认路径

            img_format = self.format_combo.currentText()
            quality = self.quality_spin.value()
            compress = self.quality_spin.value()
            height = self.height_spin.value()  # 获取目标高度
            width = self.width_spin.value()
            delete_original = self.delete_original_checkbox.isChecked()
            adjust_height = self.height_checkbox.isChecked()  # 检查复选框状态
            adjust_width = self.width_checkbox.isChecked()
            sharpness = self.sharpness_spin.value()  # 获取锐化因子
            preserve_metadata = self.preserve_metadata_checkbox.isChecked() # 保留原数据
            thread_count = int(self.cpu_combo.currentText())

            # method/speed 参数
            method = int(self.method_combo.currentText()) if img_format == 'webp' else None
            speed = int(self.speed_combo.currentText()) if img_format == 'avif' else None

            if (img_format == 'png'):
                compress = min(compress, 9)  # 限制压缩级别最大为9
            elif (img_format == 'avif'):
                compress = min(compress, 63)  # 限制压缩级别最大为63

            conversion_paused.set()  # 确保每次开始转换时为“运行”状态
            # 清理之前的线程
            if hasattr(self, 'convert_thread'):
                try:
                    if self.convert_thread.is_alive():
                        self.stop_event.set()
                        conversion_paused.set()  # 确保线程能检测到停止
                        self.convert_thread.join(timeout=0.5)
                except:
                    pass
            # 创建并启动新线程
            self.convert_thread = threading.Thread(
                target=run_conversion,
                args=(input_files, output_dir, img_format, quality, compress,
                      height, width, delete_original, adjust_height, adjust_width,
                      sharpness, conversion_paused, self.stop_event, self.log,
                      self.progress_label, preserve_metadata,
                      lambda: [
                          self.clear_input_signal.emit(),
                          delattr(self, 'convert_thread')  # 转换完成后清理线程引用
                      ],
                      thread_count,
                      method,  # 新增参数
                      speed    # 新增参数
                )
            )
            self.convert_thread.start()
            self.pause_button.setText('暂停')
            self.stop_button.setText('停止')
            self.log.info("转换已开始(点击暂停按钮可中断)")

    def clear_log(self):
        self.log_output.clear()

    def pause_conversion(self):
        """线程安全的暂停/继续控制"""
        try:
            if not hasattr(self, 'convert_thread') or not self.convert_thread.is_alive():
                return
            # 使用信号安全更新UI
            if conversion_paused.is_set():
                conversion_paused.clear()
                self.pause_button.setText('继续')
                self.log_emitter.log_message.emit("转换已暂停(点击继续按钮恢复)")
            else:
                conversion_paused.set()
                self.pause_button.setText('暂停')
                self.log_emitter.log_message.emit("转换已恢复")
            QApplication.processEvents()
        except Exception as e:
            self.log.error(f"暂停操作出错: {str(e)}")

    def clear_input_line(self):
        """清空输入路径的槽函数"""
        self.input_line.clear()
        self.log.info("输入路径已重置")

    def stop_conversion(self):
        """安全停止转换(保留输出路径)"""
        try:
            global conversion_stopped
            conversion_stopped = True
            self.stop_event.set()
            conversion_paused.set()  # 确保线程能检测停止
            
            # 仅清空输入路径
            self.clear_input_signal.emit()
            self.progress_label.setText("转换已停止")
            self.log.info("转换已停止(输出路径保留)")
            
            # 重置停止状态
            time.sleep(0.1)  # 确保线程响应
            self.stop_event.clear()
            conversion_stopped = False
        except Exception as e:
            self.log.error(f"停止出错: {str(e)}")

    def show_file_list(self):
        input_files = self.input_line.text().split(";")
        if not input_files:
            self.log.info('未选择输入文件或文件夹')
            return

        files = []
        if len(input_files) == 1 and Path(input_files[0]).is_dir():  # 输入是目录
            for filename in Path(input_files[0]).iterdir():
                if filename.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
                    files.append(str(filename))
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

    def save_settings(self):
        """保存当前设置到ini文件"""
        self.config['Main'] = {
            'format': self.format_combo.currentText(),
            'quality': str(self.quality_spin.value()),
            'height': str(self.height_spin.value()),
            'width': str(self.width_spin.value()),
            'height_checked': str(self.height_checkbox.isChecked()),
            'width_checked': str(self.width_checkbox.isChecked()),
            'sharpness': str(self.sharpness_spin.value()),
            'delete_original': str(self.delete_original_checkbox.isChecked()),
            'preserve_metadata': str(self.preserve_metadata_checkbox.isChecked()),
            'cpu_threads': self.cpu_combo.currentText(),
            'method': self.method_combo.currentText(),
            'speed': self.speed_combo.currentText()
        }
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)
        self.log.info("设置已保存到 settings.ini")

    def load_settings(self):
        """加载ini文件设置"""
        if not os.path.exists(self.config_path):
            return
        self.config.read(self.config_path, encoding='utf-8')
        if 'Main' not in self.config:
            return
        s = self.config['Main']
        fmt = s.get('format', 'avif')
        idx = self.format_combo.findText(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        self.quality_spin.setValue(int(s.get('quality', self.quality_spin.value())))
        self.height_spin.setValue(int(s.get('height', self.height_spin.value())))
        self.width_spin.setValue(int(s.get('width', self.width_spin.value())))
        self.height_checkbox.setChecked(s.get('height_checked', 'True') == 'True')
        self.width_checkbox.setChecked(s.get('width_checked', 'False') == 'True')
        self.sharpness_spin.setValue(float(s.get('sharpness', self.sharpness_spin.value())))
        self.delete_original_checkbox.setChecked(s.get('delete_original', 'False') == 'True')
        self.preserve_metadata_checkbox.setChecked(s.get('preserve_metadata', 'True') == 'True')
        cpu_idx = self.cpu_combo.findText(s.get('cpu_threads', self.cpu_combo.currentText()))
        if cpu_idx >= 0:
            self.cpu_combo.setCurrentIndex(cpu_idx)
        self.method_combo.setCurrentText(s.get('method', '6'))
        self.speed_combo.setCurrentText(s.get('speed', '4'))
        self.log.info("设置已从 settings.ini 加载")

    def reset_settings(self):
        """重置为默认设置"""
        self.input_line.clear()
        self.output_line.clear()
        self.format_combo.setCurrentText('avif')
        self.quality_spin.setValue(63)
        self.height_spin.setValue(768)
        self.width_spin.setValue(1500)
        self.height_checkbox.setChecked(True)
        self.width_checkbox.setChecked(False)
        self.sharpness_spin.setValue(1.0)
        self.delete_original_checkbox.setChecked(False)
        self.preserve_metadata_checkbox.setChecked(True)
        self.cpu_combo.setCurrentText(str(multiprocessing.cpu_count()))
        self.method_combo.setCurrentText("6")
        self.speed_combo.setCurrentText("4")
        self.log.info("设置已重置为默认值")

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
