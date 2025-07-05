# PyOxidizer 配置文件 for AVJPWConverterPyQt5
# 适用于 PyQt5 GUI 打包

def make_dist():
    dist = default_python_distribution()

    policy = dist.make_python_packaging_policy()
    # 简化资源策略配置
    policy.resources_location = "in-memory"
    policy.resources_location_fallback = "in-memory"
    policy.include_distribution_sources = True
    policy.include_distribution_resources = True
    policy.include_test = False
    policy.file_scanner_emit_files = False

    python_config = dist.make_python_interpreter_config()
    # 修正编码初始化和优化级别配置
    python_config.run_command = "import sys, encodings.utf_8;from AVJPWConverterPyQt5 import main;main()"
    python_config.filesystem_importer = False
    python_config.oxidized_importer = True
    python_config.legacy_windows_stdio = False
    python_config.optimization_level = 2  # 使用正确的属性名
    
    exe = dist.to_python_executable(
        name="avjpwconverter_pyqt5",
        packaging_policy=policy,
        config=python_config,
    )

    # 改进依赖安装配置
    exe.add_python_resources(exe.pip_install([
        "PyQt5",
        "PyQt5-sip",
    ]))
    
    # 简化应用代码添加方式
    exe.add_python_resource(".", ["AVJPWConverterPyQt5.py"])
    
    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    # 修正输出路径并确保目录存在
    install_dir = "build/x86_64-pc-windows-msvc/release/install"
    files.add_location(install_dir, exe)
    # 添加程序所需的其他资源
    files.add_source(exe.read_virtualenv_dir(), install_dir)
    return files

# 删除错误的release参数
register_target("dist", make_dist)
register_target("resources", make_embedded_resources, depends=["dist"])
register_target("install", make_install, depends=["dist"])
resolve_targets()
