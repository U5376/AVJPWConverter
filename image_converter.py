import os
import sys
import argparse
from PIL import Image, ImageEnhance
from loguru import logger

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
        logger.debug(f"开始转换图片: {input_path}")
        img = Image.open(input_path)
        
        # 处理图像模式转换
        if img.mode == 'RGBA' and img_format.lower() in ['jpg', 'jpeg']:
            logger.debug("RGBA图像转换为RGB模式(JPEG格式需要)")
            img = img.convert('RGB')
        elif img.mode == 'P':
            logger.debug("保持调色板图像原模式")
        
        # 调整大小（保持比例）
        if width or height:
            orig_width, orig_height = img.size
            if not width: width = orig_width
            if not height: height = orig_height
            ratio = min(width/orig_width, height/orig_height)
            new_size = (int(orig_width*ratio), int(orig_height*ratio))
            logger.debug(f"调整大小: {img.size} -> {new_size}")
            img = img.resize(new_size, Image.LANCZOS)
        
        # 锐化处理(跳过调色板图像)
        if sharpness != 1.0 and img.mode != 'P':
            logger.debug(f"应用锐化: {sharpness}")
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
        
        # 规范化输出路径
        output_path = os.path.normpath(output_path)
        output_dir = os.path.dirname(output_path) or '.'  # 处理当前目录情况
        
        # 确保输出目录存在(仅在需要时创建)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"无法创建输出目录: {output_dir}")
                raise
        
        try:
            # 创建输出目录(如果不存在)
            os.makedirs(output_dir, exist_ok=True)
            
            # 验证目录可写性
            if not os.path.isdir(output_dir):
                raise NotADirectoryError(f"输出路径不是目录: {output_dir}")
                
            if not os.access(output_dir, os.W_OK):
                raise PermissionError(f"无写入权限: {output_dir}")
                
            # 验证输出文件名有效性
            if not os.path.basename(output_path):
                raise ValueError("无效的输出文件名")
            
            logger.debug(f"尝试保存到: {output_path}")
            img.save(output_path, **save_args)
            
        except Exception as e:
            logger.error(f"路径处理失败: {output_path}")
            raise
        logger.success(f"成功转换: {output_path}")
        return True
    except Exception as e:
        error_type = type(e).__name__
        if "cannot filter palette images" in str(e):
            logger.error(f"调色板图像转换失败，请手动处理: {input_path}")
        elif "corrupt image" in str(e):
            logger.error(f"损坏的图像文件: {input_path}")
        else:
            logger.error(f"转换失败 ({error_type}): {input_path}")
            logger.exception(e)  # 输出完整错误堆栈
        return False

if __name__ == "__main__":
    # 配置logger
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")

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
                        full_path = os.path.join(root, f)
                        inputs.append(full_path)
        else:
            logger.warning(f"跳过无效路径: {path}")

    if not inputs:
        logger.error("错误：未找到有效的输入文件")
        sys.exit(1)

    logger.info(f"共找到 {len(inputs)} 个待转换文件")
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

            logger.info(f"{os.path.basename(input_file)} → {os.path.basename(output_file)}")

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
                logger.error(f"状态: 失败")
        except Exception as e:
            logger.exception(f"处理异常: {str(e)}")

    logger.info(f"图片转换成功: {success_count}/{len(inputs)}")
    logger.info(f"失败数量: {len(inputs) - success_count}")
