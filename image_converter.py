import os
import sys
import argparse
from PIL import Image, ImageEnhance

def convert_image(
    input_path,
    output_path=None,
    img_format="webp",
    quality=85,
    width=None,
    height=None,
    sharpness=1.0
):
    try:
        img = Image.open(input_path)
        
        # 调整大小（保持比例）
        if width or height:
            orig_width, orig_height = img.size
            if not width: width = orig_width
            if not height: height = orig_height
            ratio = min(width/orig_width, height/orig_height)
            new_size = (int(orig_width * ratio), int(orig_height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # 锐化处理
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)
        
        # 确定输出路径
        if not output_path:
            base = os.path.splitext(input_path)[0]
            output_path = f"{base}.{img_format}"
        
        # 保存参数
        save_args = {}
        if img_format in ["jpg", "jpeg", "webp"]:
            save_args["quality"] = quality
        elif img_format == "png":
            save_args["compress_level"] = min(quality//10, 9)
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        img.save(output_path, **save_args)
        return True
    except Exception as e:
        print(f"Error converting {input_path}: {str(e)}", file=sys.stderr)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI Image Converter (支持多文件/目录)")
    parser.add_argument("-i", "--input", nargs='+', required=True,
                      help="输入文件或目录（支持多个路径）")
    parser.add_argument("--input-list", action="store_true",
                      help=argparse.SUPPRESS)  # 隐藏参数，内部使用
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument("-f", "--format", default="webp", 
                      choices=["webp", "jpg", "png", "jpeg"])
    parser.add_argument("-q", "--quality", type=int, default=80)
    parser.add_argument("-W", "--width", type=int, help="调整宽度（保持比例）")
    parser.add_argument("-H", "--height", type=int, help="调整高度（保持比例）")
    parser.add_argument("-s", "--sharpness", type=float, default=1.0,
                      help="锐化强度（1.0为原图，<1.0模糊，>1.0锐化，建议0.5-2.0）")
    
    args = parser.parse_args()

    # 处理文件列表输入
    if len(args.input) == 1 and args.input[0].startswith('@'):
        list_file = args.input[0][1:]  # 去掉@符号
        try:
            with open(list_file, 'r', encoding='utf-8') as f:
                args.input = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"无法读取列表文件 {list_file}: {str(e)}", file=sys.stderr)
            sys.exit(1)

    # 收集所有输入文件
    inputs = []
    for path in args.input:
        if os.path.isfile(path):
            if path.lower().endswith((".png", ".jpg", ".jpeg")):
                inputs.append(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg")):
                        inputs.append(os.path.join(root, f))
        else:
            print(f"警告：跳过无效路径 {path}", file=sys.stderr)

    if not inputs:
        print("错误：未找到有效的输入文件", file=sys.stderr)
        sys.exit(1)

    # 批量转换
    success_count = 0
    for input_file in inputs:
        try:
            # 构建输出路径
            if args.output:
                filename = f"{os.path.splitext(os.path.basename(input_file))[0]}.{args.format}"
                output_file = os.path.join(args.output, filename)
            else:
                output_dir = os.path.dirname(input_file)
                filename = f"{os.path.splitext(os.path.basename(input_file))[0]}.{args.format}"
                output_file = os.path.join(output_dir, filename)

            # 简化的日志输出
            print(f"{os.path.basename(input_file)} → {os.path.basename(output_file)}")

            if convert_image(
                input_file,
                output_file,
                args.format,
                args.quality,
                args.width,
                args.height,
                args.sharpness
            ):
                success_count += 1
            else:
                print(f"{os.path.basename(input_file)} → 失败")  # 失败专用日志
        except Exception as e:
            print(f"{os.path.basename(input_file)} → 异常: {str(e)}")

    # 最终统计
    print(f"\n转换完成: 成功 {success_count} 个")
    print(f"失败数量: {len(inputs) - success_count}")