[app]


# 应用信息
title = 小说阅读器
package.name = NovelReader
package.domain = com.novelreader

# 源码
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,otf

# 版本
version = 0.1

# 需求库
requirements = python3,kivy==2.3.1,requests,beautifulsoup4,sqlalchemy

# 权限
android.permissions = INTERNET

# Android 配置
android.api = 34
android.minapi = 21
android.ndk = 27
android.sdk = 34
android.gradle_dependencies = 'androidx.core:core:1.7.0'
android.enable_androidx = True

# 图标
# android.icon = app/icon.png

# 打包格式
android.archs = arm64-v8a
android.accept_sdk_license = True

# 启动脚本
osx.python_version = 3
ios.python_version = 3

# 构建输出
android.binary_packages_output = bin/
