# PyOxidizer 配置文件 for AVJPWConverterPyQt5
# 适用于 PyQt5 GUI 打包

def make_dist():
    dist = default_python_distribution()

    policy = dist.make_python_packaging_policy()
    # 改为文件系统模式
    policy.resources_location = "filesystem-relative:lib"
    policy.resources_location_fallback = "filesystem-relative:lib"
    policy.include_distribution_sources = True
    policy.include_distribution_resources = True
    policy.include_test = False
    policy.file_scanner_emit_files = True  # 启用文件扫描

    python_config = dist.make_python_interpreter_config()
    python_config.filesystem_importer = True
    python_config.oxidized_importer = True
    
    exe = dist.to_python_executable(
        name="avjpwconverter_pyqt5",
        packaging_policy=policy,
        config=python_config,
    )

    # 添加PyQt5依赖
    exe.add_python_resources(exe.pip_install([
        "PyQt5",
        "PyQt5-sip",
    ]))
    
    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    # 修改为正确的目标路径
    install_dir = "build/x86_64-pc-windows-msvc/release/install"
    files.add_location(install_dir, exe)
    return files

register_target("dist", make_dist)
register_target("resources", make_embedded_resources, depends=["dist"])
register_target("install", make_install, depends=["dist"])
resolve_targets()
