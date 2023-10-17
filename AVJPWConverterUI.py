import os
import threading
import logging
import time
from tkinter import filedialog, END
from PIL import Image
import pillow_avif
import PySimpleGUI as sg

# 设置UI界面的字体为宋体
sg.set_options(font=("宋体", 12))

def select_input_dir(window):
    input_dir = filedialog.askdirectory()
    window['-IN-'].update(value=input_dir)  # 将选择的路径更新到输入框中
    log.info(f"选择的输入目录是: {input_dir}")

def select_output_dir(window):
    output_dir = filedialog.askdirectory()
    window['-OUT-'].update(value=output_dir)  # 将选择的路径更新到输入框中
    log.info(f"选择的输出目录是: {output_dir}")

class TextHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        window['-OUTLOG-'].print(msg)

log = logging.getLogger()
log.setLevel(logging.INFO)

handler = TextHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))  # 修改时间显示格式
log.handlers = [handler]

# 全局变量用来控制转换过程
conversion_paused = False 

def convert_images(input_dir, output_dir, img_format, quality, compress):
    convert_thread = threading.Thread(target=run_conversion, args=(input_dir, output_dir, img_format, quality, compress, conversion_paused))
    convert_thread.start()

def run_conversion(input_dir, output_dir, img_format, quality, compress, pause_event):
    log.info("开始转换过程：")

    # 遍历目录
    for file in os.listdir(input_dir):
        if file.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".avif")):
            pause_event.wait()  # 如果 pause_event 内部标志为 True 就立即返回，否则阻塞直至内部标志为 True

            max_try = 3  # 最大重试次数
            try_count = 0  # 重试计数器

            while try_count < max_try:
                try:
                    log.info(f"正在转换图片 {file}")

                    image_path = os.path.join(input_dir, file) 
                    image = Image.open(image_path)

                    # 生成新的文件名，其扩展名改为所需格式
                    new_file_name = os.path.splitext(file)[0] + '.' + img_format
                    new_file_path = os.path.join(output_dir, new_file_name)

                    # 变换图像并保存
                    if img_format in ["jpg", "jpeg", "webp", "avif"]:
                        image.save(new_file_path, quality=quality)
                    elif img_format == "png":
                         image.save(new_file_path, compress_level=compress)

                    log.info(f"{file} 成功转换为 {img_format} 格式！")
                    break  # 转换成功，跳出循环
                except Exception as e:
                    log.error(f"转换 {file} 失败。错误原因: {e}")
                    log.info(f"正在重试转换 {file}")
                    try_count += 1
                    time.sleep(1)  # 等待一秒后重试

            if try_count == max_try:
                 log.error(f"转换 {file} 失败次数超过最大重试次数，跳过转换")
    log.info("所有图像转换已完成！")  # 所有图片都已转换完成，输出信息
conversion_paused = threading.Event()

layout = [
    [sg.Button('输入路径', key='-INPUT-', enable_events=True, size=(10, 1)), sg.Input(enable_events=True, readonly=False, key='-IN-', size=(60, 1))],
    [sg.Button('输出路径', key='-OUTPUT-', enable_events=True, size=(10, 1)), sg.Input(enable_events=True, readonly=False, key='-OUT-', size=(60, 1))],
    [sg.Text('图片格式: '), sg.Combo(['jpg', 'png', 'webp', 'avif'], default_value='jpg', key='-FORMAT-', size=(5, 1), enable_events=True)],
    [sg.Text('JPEG 质量 (1-100，默认值为 90):', key='-QUALITY_TEXT-'), sg.Spin(values=list(range(1, 101)), initial_value=90, key='-COMPRESS_QUALITY-', size=(4, 1))],
    [sg.Button('开始转换', key='-CONVERT-', enable_events=True, size=(10, 1)),
     sg.Button('暂停/停止', key='-PAUSE-', enable_events=True, size=(10, 1)),
     sg.Button('打开输出文件夹', key='-OPENOUT-', enable_events=True, size=(15, 1)),
     sg.Button('清空日志', key='-CLEARLOG-', enable_events=True, size=(10, 1), pad=((160, 0), (0, 0)))],
    [sg.Output(size=(70,20), key='-OUTLOG-')]
]

window = sg.Window('AVJPWConverterUI', layout)

while True:
    event, values = window.read()

    if event == sg.WINDOW_CLOSED:
        break
    elif event == '-INPUT-':
        select_input_dir(window)
    elif event == '-OUTPUT-':
        select_output_dir(window)
    elif event == '-OPENOUT-':
        output_dir = values['-OUT-']
        if output_dir == '':
            output_dir = os.path.join(values['-IN-'], 'processed')
            os.makedirs(output_dir, exist_ok=True)
        os.startfile(output_dir)
    elif event == '-FORMAT-':
        img_format = values['-FORMAT-']
        if img_format == 'jpg':
            window['-QUALITY_TEXT-'].update('JPEG 质量 (1-100，默认值为 90):')
            window['-COMPRESS_QUALITY-'].update(value='90')
        elif img_format == 'png':
            window['-QUALITY_TEXT-'].update('PNG 压缩级别 (0-9，默认值为 6):')
            window['-COMPRESS_QUALITY-'].update(value='6')
        elif img_format == 'webp':
            window['-QUALITY_TEXT-'].update('WEBP 质量 (1-100，默认值为 90):')
            window['-COMPRESS_QUALITY-'].update(value='90')
        elif img_format == 'avif':
            window['-QUALITY_TEXT-'].update('AVIF 质量 (1-63，默认值为 50):')
            window['-COMPRESS_QUALITY-'].update(value='50')
    elif event == '-CONVERT-':
        if values['-IN-'] == '':
            sg.Popup('请选择输入的文件夹', keep_on_top=True)
        else:
            # 设置输入和输出路径，如果输出路径为空，那么在输入路径下创建 processed 子文件夹
            input_dir = values['-IN-']
            output_dir = values['-OUT-']
            if output_dir == '':
                output_dir = os.path.join(input_dir, 'processed')
                os.makedirs(output_dir, exist_ok=True)  # 允许目录已存在
                log.info(f"输出路径为空，将在输入路径下创建文件夹processed")

            img_format = values['-FORMAT-']
            quality = int(values['-COMPRESS_QUALITY-'])
            compress = int(values['-COMPRESS_QUALITY-'])
            if img_format == 'png':
                compress = min(compress, 9)  # 限制压缩级别最大为9
            elif img_format == 'avif':
                compress = min(compress, 63)  # 限制压缩级别最大为63

            conversion_paused.set() 
            convert_images(input_dir, output_dir, img_format, quality, compress)
            window['-PAUSE-'].update(text='暂停')  # 更新按钮文本
    elif event == '-CLEARLOG-':
        window['-OUTLOG-'].update('')  # 清空日志输出
    elif event == '-PAUSE-':
        if conversion_paused.is_set():
            conversion_paused.clear()
            window['-PAUSE-'].update(text='继续')
            log.info('转换已暂停')
        else:
            conversion_paused.set()
            window['-PAUSE-'].update(text='暂停')
            log.info('转换已继续')

window.close()
