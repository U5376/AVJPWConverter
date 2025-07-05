# PyOxidizer 配置文件 for AVJPWConverterPyQt5
# 适用于 PyQt5 GUI 打包

def make_dist():
    dist = default_python_distribution()

    policy = dist.make_python_packaging_policy()
    # 包含所有必要的运行时文件
    policy.resources_location = "filesystem-relative:lib"
    policy.resources_location_fallback = "filesystem-relative:lib"
    policy.include_distribution_sources = True
    policy.include_distribution_resources = True
    policy.include_test = False
    policy.file_scanner_emit_files = True
    policy.include_non_distribution_sources = True  # 添加非发布源
    # 删除不支持的 include_package_data 配置

    python_config = dist.make_python_interpreter_config()
    python_config.run_command = "from AVJPWConverterPyQt5 import main;main()"
    python_config.filesystem_importer = True
    python_config.oxidized_importer = True
    
    exe = dist.to_python_executable(
        name="avjpwconverter_pyqt5",
        packaging_policy=policy,
        config=python_config,
    )

    # 让 PyOxidizer 自动检测和打包所有依赖
    exe.add_python_resources(exe.pip_install([
        ".",  # 安装当前目录(主程序)
        "PyQt5",  # 显式添加 PyQt5 以确保完整性
    ]))
    
    # 添加基本配置
    exe.windows_subsystem = "windows"
    
    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    install_dir = "build/x86_64-pc-windows-msvc/release/install"
    files.add_location(install_dir, exe)
    
    # 添加Qt运行时文件
    qt_dirs = [
        "platforms",
        "styles",
        "imageformats",
    ]
    for qt_dir in qt_dirs:
        files.add_source("lib/site-packages/PyQt5/Qt5/plugins/%s" % qt_dir, "%s/%s" % (install_dir, qt_dir))
    
    return files

register_target("dist", make_dist)
register_target("resources", make_embedded_resources, depends=["dist"])
register_target("install", make_install, depends=["dist"])
resolve_targets()
