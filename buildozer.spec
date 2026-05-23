[app]

title = 小说阅读器
package.name = NovelReaderApp
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

android.archs = arm64-v8a
android.accept_sdk_license = True

android.binary_packages_output = bin/
