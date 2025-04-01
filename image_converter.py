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
    sharpness=1.0  # 默认值1.0表示不锐化
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
        
        # 锐化处理（仅当sharpness≠1.0时生效）
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)
        
        # 确定输出路径
        if not output_path:
            base = os.path.splitext(input_path)[0]
            output_path = f"{base}.{img_format}"
        
        # 保存图片
        save_args = {}
        if img_format in ["jpg", "jpeg", "webp"]:
            save_args["quality"] = quality
        elif img_format == "png":
            save_args["compress_level"] = min(quality//10, 9)
        
        img.save(output_path, **save_args)
        return True
    except Exception as e:
        print(f"Error converting {input_path}: {str(e)}", file=sys.stderr)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI Image Converter")
    parser.add_argument("-i", "--input", required=True, help="输入文件或目录")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument("-f", "--format", default="webp", choices=["webp", "jpg", "png"])
    parser.add_argument("-q", "--quality", type=int, default=80)
    parser.add_argument("-W", "--width", type=int, help="调整宽度（保持比例）")
    parser.add_argument("-H", "--height", type=int, help="调整高度（保持比例）")
    parser.add_argument("-s", "--sharpness", type=float, default=1.0, 
                       help="锐化强度（1.0为原图，<1.0模糊，>1.0锐化，范围0.5-2.0）")
    args = parser.parse_args()

    # 处理输入
    inputs = []
    if os.path.isdir(args.input):
        for root, _, files in os.walk(args.input):
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    inputs.append(os.path.join(root, f))
    else:
        inputs = [args.input]

    # 批量转换
    for input_file in inputs:
        output_dir = args.output or os.path.dirname(input_file)
        output_file = os.path.join(
            output_dir,
            f"{os.path.splitext(os.path.basename(input_file))[0]}.{args.format}"
        )
        convert_image(
            input_file,
            output_file,
            args.format,
            args.quality,
            args.width,
            args.height,
            args.sharpness  # 传递锐化参数
        )