[app]

title = 小说阅读器
package.name = NovelReader
package.domain = com.novelreader

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,otf

version = 0.1

requirements = python3,kivy,requests,beautifulsoup4,sqlalchemy

android.permissions = INTERNET

android.api = 34
android.minapi = 21
android.ndk = 27
android.sdk = 34

android.gradle_dependencies = androidx.core:core:1.7.0
android.enable_androidx = True

android.archs = arm64-v8a
android.accept_sdk_license = True

android.binary_packages_output = bin/

# 允许解压所有文件到私有目录（避免 SQLite 路径问题）
android.copy_libs = True

# 设置应用全屏
android.fullscreen = 0

# 指定 Python 版本（覆盖默认）
android.python_version = 3.11

# 日志级别
android.logcat_filters = *:S python:D
