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
            new_size = (int(orig_width*ratio), int(orig_height*ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # 处理图像模式转换
        if img.mode == 'RGBA' and img_format.lower() in ['jpg', 'jpeg']:
            print(f"RGBA图像转换为RGB模式(JPEG格式需要)")
            img = img.convert('RGB')
        elif img.mode == 'P':
            print(f"保持调色板图像原模式")

        # 锐化处理(跳过调色板图像)
        if sharpness != 1.0 and img.mode != 'P':
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
        return {
            'success': True,
            'mode': img.mode,
            'total': 1,  # 单次转换总是1
            'converted': 1  # 成功转换计数
        }
    except Exception as e:
        print(f"Error converting {input_path}: {str(e)}", file=sys.stderr)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI Image Converter (支持多文件/目录)")
    parser.add_argument("-i", "--input", nargs='+', required=True,
                       help="输入文件或目录（支持多个路径）")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument("-f", "--format", default="webp", 
                       choices=["webp", "jpg", "png", "jpeg"])
    parser.add_argument("-q", "--quality", type=int, default=80)
    parser.add_argument("-W", "--width", type=int, help="调整宽度（保持比例）")
    parser.add_argument("-H", "--height", type=int, help="调整高度（保持比例）")
    parser.add_argument("-s", "--sharpness", type=float, default=1.0,
                       help="锐化强度（1.0为原图，<1.0模糊，>1.0锐化，建议0.5-2.0）")
    parser.add_argument("--success", type=int, help="成功数量")
    parser.add_argument("--failed", type=int, help="失败数量")
    
    args = parser.parse_args()

    # 收集所有输入文件
    inputs = []
    for path in args.input:
        # 检查路径是否以 @ 开头（表示文件列表）
        if path.startswith('@'):
            file_list_path = path[1:]  # 去掉 @ 符号
            try:
                with open(file_list_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        file_path = line.strip().strip('"')  # 处理带空格的路径
                        # 递归处理文件列表中的路径（支持文件和目录）
                        if os.path.isfile(file_path):
                            if file_path.lower().endswith((".png", ".jpg", ".jpeg")):
                                inputs.append(file_path)
                        elif os.path.isdir(file_path):
                            for root, _, files in os.walk(file_path):
                                for f in files:
                                    if f.lower().endswith((".png", ".jpg", ".jpeg")):
                                        inputs.append(os.path.join(root, f))
                        else:
                            print(f"警告：跳过无效路径 {file_path}", file=sys.stderr)
            except FileNotFoundError:
                print(f"错误：文件列表 {file_list_path} 不存在", file=sys.stderr)
                sys.exit(1)
        else:
            # 处理普通文件或目录
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

    # 批量转换
    success_count = 0
    for i, input_file in enumerate(inputs, 1):
        try:
            # 构建输出路径
            if args.output:
                filename = f"{os.path.splitext(os.path.basename(input_file))[0]}.{args.format}"
                output_file = os.path.join(args.output, filename)
            else:
                output_dir = os.path.dirname(input_file)
                filename = f"{os.path.splitext(os.path.basename(input_file))[0]}.{args.format}"
                output_file = os.path.join(output_dir, filename)

            print(f"\n[{i}/{len(inputs)}] 正在处理: {os.path.basename(input_file)}")
            print(f"输入路径: {input_file}")
            print(f"输出路径: {output_file}")

            result = convert_image(
                input_file,
                output_file,
                args.format,
                args.quality,
                args.width,
                args.height,
                args.sharpness
            )
            if result and result.get('success'):
                success_count += 1
                print(f"状态: 成功 (模式: {result['mode']})")  # 修复img_mode未定义的问题
            else:
                print("状态: 失败")
        except Exception as e:
            print(f"处理异常: {str(e)}")

    print(f"\n转换完成: 成功 {success_count}/{len(inputs)}")
    print(f"失败数量: {len(inputs) - success_count}")
