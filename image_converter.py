import os
import sys
import argparse
from PIL import Image, ImageEnhance
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        # 检查输入文件是否存在
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"输入文件 {input_path} 不存在")

        img = Image.open(input_path)
        
        # 调整大小（保持比例）
        if width or height:
            orig_width, orig_height = img.size
            if not width: width = orig_width
            if not height: height = orig_height
            ratio = min(width/orig_width, height/orig_height)
            new_size = (int(orig_width*ratio), int(orig_height*ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # 处理图像模式转换
        if img.mode == 'RGBA' and img_format.lower() in ['jpg', 'jpeg']:
            img = img.convert('RGB')
        elif img.mode == 'P':
            print(f"保持调色板图像原模式")

        # 锐化处理(跳过调色板图像)
        if sharpness != 1.0 and img.mode != 'P':
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)
        
        # 确定输出路径
        if not output_path:
            # 规范化输入路径的目录和文件名
            input_dir, input_filename = os.path.split(input_path)
            input_base = os.path.splitext(input_filename)[0]
            # 如果输入目录为空，使用当前工作目录
            output_dir = os.path.normpath(input_dir) if input_dir else os.getcwd()
            output_path = os.path.join(output_dir, f"{input_base}.{img_format}")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 保存参数
        save_args = {}
        if img_format in ["jpg", "jpeg", "webp"]:
            save_args["quality"] = quality
        elif img_format == "png":
            save_args["compress_level"] = min(quality//10, 9)
        
        img.save(output_path, **save_args)
        return {
            'success': True,
            'mode': img.mode
        }
    except Exception as e:
        print(f"Error converting {input_path}: {str(e)}", file=sys.stderr)
        return {'success': False}

def expand_input_paths(inputs):
    """递归解析输入路径，支持文件列表和嵌套路径"""
    expanded_paths = []
    for path in inputs:
        if path.startswith('@'):
            list_file = path[1:]
            try:
                with open(list_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip().strip('"')  # 处理带引号的路径
                        normalized_path = os.path.normpath(line)  # 规范化路径
                        expanded_paths.extend(expand_input_paths([normalized_path]))
            except Exception as e:
                print(f"错误：无法读取文件列表 {list_file} - {str(e)}", file=sys.stderr)
                sys.exit(1)
        else:
            expanded_paths.append(os.path.normpath(path))  # 处理普通路径
    return expanded_paths

def process_single_image(i, input_file, total, args):
    try:
        input_path = os.path.abspath(input_file)
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"输入文件 {input_path} 不存在")

        if args.output:
            output_dir = os.path.abspath(args.output)
            filename = f"{os.path.splitext(os.path.basename(input_file))[0]}.{args.format}"
            output_file = os.path.join(output_dir, filename)
        else:
            output_dir = os.path.dirname(input_path) or os.getcwd()
            filename = f"{os.path.splitext(os.path.basename(input_file))[0]}.{args.format}"
            output_file = os.path.join(output_dir, filename)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        print(f"[{i}/{total}] {os.path.basename(input_file)} → {os.path.basename(output_file)}")

        result = convert_image(
            input_path,
            output_file,
            args.format,
            args.quality,
            args.width,
            args.height,
            args.sharpness
        )
        return (input_file, result)
    except Exception as e:
        print(f"严重异常：{str(e)}")
        return (input_file, {'success': False, 'error': str(e)})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI Image Converter (支持多文件/目录)")
    parser.add_argument("-i", "--input", nargs='+', required=True,
                       help="输入文件、目录或文件列表（支持 @list.txt 格式）")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument("-f", "--format", default="webp", 
                       choices=["webp", "jpg", "png", "jpeg"])
    parser.add_argument("-q", "--quality", type=int, default=80)
    parser.add_argument("-W", "--width", type=int, help="调整宽度（保持比例）")
    parser.add_argument("-H", "--height", type=int, help="调整高度（保持比例）")
    parser.add_argument("-s", "--sharpness", type=float, default=1.0,
                       help="锐化强度（默认 1.0，<1.0 模糊，>1.0 锐化，建议 0.5-2.0）")
    
    args = parser.parse_args()

    # 递归解析输入路径
    expanded_inputs = expand_input_paths(args.input)

    # 收集有效文件
    inputs = []
    for path in expanded_inputs:
        if os.path.isfile(path) and path.lower().endswith((".png", ".jpg", ".jpeg")):
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

    # 多线程批量转换
    success_count = 0
    total = len(inputs)
    max_workers = min(8, total)  # 可根据需要调整线程数

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_single_image, i+1, input_file, total, args)
            for i, input_file in enumerate(inputs)
        ]
        for future in as_completed(futures):
            input_file, result = future.result()
            if result.get('success'):
                success_count += 1
            else:
                print(f"失败：{os.path.basename(input_file)} - {result.get('error', '未知错误')}")

    print(f"\n转换完成: 成功 {success_count}/{len(inputs)}")
    print(f"失败数量: {len(inputs) - success_count}")