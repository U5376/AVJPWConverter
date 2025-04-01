import os
import sys
import argparse
from PIL import Image, ImageEnhance

def convert_image(input_path, output_path, img_format, quality, width, height, sharpness):
    """核心转换函数（增加日志输出）"""
    try:
        img = Image.open(input_path)
        
        # 调整大小（保持比例）
        if width or height:
            orig_width, orig_height = img.size
            ratio = min(
                (width or orig_width)/orig_width,
                (height or orig_height)/orig_height
            )
            img = img.resize(
                (int(orig_width*ratio), int(orig_height*ratio)),
                Image.LANCZOS
            )
        
        # 锐化处理
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)
        
        # 保存参数
        save_args = {}
        if img_format in ["jpg", "jpeg", "webp"]:
            save_args["quality"] = quality
        elif img_format == "png":
            save_args["compress_level"] = min(quality//10, 9)
        
        img.save(output_path, **save_args)
        print(f"Success: {os.path.basename(input_path)} → {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"Error: {os.path.basename(input_path)} → {str(e)}", file=sys.stderr)
        return False

def process_file(args, input_file):
    """文件处理逻辑"""
    # 构建输出路径（覆盖模式）
    if args.output:  # 指定输出目录
        rel_path = os.path.relpath(input_file, args.input)
        output_file = os.path.join(args.output, rel_path)
        output_file = os.path.splitext(output_file)[0] + f".{args.format}"
    else:  # 覆盖原文件
        output_file = os.path.splitext(input_file)[0] + f".{args.format}"
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    return convert_image(
        input_file,
        output_file,
        args.format,
        args.quality,
        args.width,
        args.height,
        args.sharpness
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="增强版图片转换工具")
    parser.add_argument("-i", "--input", required=True, help="输入文件或目录")
    parser.add_argument("-o", "--output", help="输出目录（不指定则覆盖原文件）")
    parser.add_argument("-f", "--format", default="webp", choices=["webp", "jpg", "png"])
    parser.add_argument("-q", "--quality", type=int, default=80)
    parser.add_argument("-W", "--width", type=int, help="调整宽度（保持比例）")
    parser.add_argument("-H", "--height", type=int, help="调整高度（保持比例）")
    parser.add_argument("-s", "--sharpness", type=float, default=1.0,
                      help="锐化强度（0.5-2.0）")
    args = parser.parse_args()

    # 收集文件列表
    inputs = []
    if os.path.isdir(args.input):
        for root, _, files in os.walk(args.input):
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    inputs.append(os.path.join(root, f))
    else:
        inputs = [args.input]

    # 批量处理
    success = 0
    for input_file in inputs:
        if process_file(args, input_file):
            success += 1
    
    print(f"\n转换完成：成功 {success}/{len(inputs)}")
    sys.exit(0 if success == len(inputs) else 1)