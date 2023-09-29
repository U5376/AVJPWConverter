import os
from PIL import Image
import pillow_avif

print("图片文件格式转换.")
print("支持avif.png.jpg/jpeg.webp格式互相转换")
input_dir = input("请输入输入目录的路径: ")

# 获取输入目录所有文件
all_files = os.listdir(input_dir)

# 支持的输入文件格式
supported_formats = ['.avif', '.png', '.jpeg', '.jpg', '.webp']

# 确定符合要求的文件列表
input_files = [f for f in all_files if os.path.splitext(f)[-1].lower() in supported_formats]

if not input_files:
    print("在输入目录内未找到支持的文件格式。")
    exit()

output_dir = input("请输入输出目录的路径: ")
output_format = input("请输入输出的图片格式（png， jpg, webp 或 avif）: ").lower()

if output_format == 'jpg':
    quality = int(input("请输入 JPEG 质量 (1-100，默认值为 90): ") or "90")
elif output_format == 'png':
    compress_level = int(input("请输入 PNG 压缩级别 (0-9，默认值为 6): ") or "6")
elif output_format == 'webp':
    quality = int(input("请输入 WEBP 质量 (1-100，默认值为 90): ") or "90")
elif output_format == 'avif':
    quality = int(input("请输入 AVIF 质量 (1-63，默认值为 50): ") or "50")

for file in input_files:
    # 使用Pillow打开图片
    img = Image.open(os.path.join(input_dir, file))

    # 输出为选择的格式
    output_name = f'{os.path.splitext(file)[0]}.{output_format}'
    output_path = os.path.join(output_dir, output_name)

    # 根据选定的格式进行保存
    if output_format == 'jpg':
        img.save(output_path, 'JPEG', quality=quality)
    elif output_format == 'png':
        img.save(output_path, 'PNG', optimize=True, compress_level=compress_level)
    elif output_format == 'webp':
        img.save(output_path, 'WEBP', quality=quality)
    elif output_format == 'avif':
        img.save(output_path, 'AVIF', quality=quality)
    else:
        print("无法识别的格式 {}. 跳过 {} 文件.".format(output_format, file))
        continue

    print(f"{file} 已成功转换为 {output_name}")

print("转换完成!")
