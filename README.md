# ZhipuSearch Plugin

一个基于智谱AI的搜索插件，支持知乎、必应等多源搜索。

## 功能特点

- 支持多个搜索源（知乎、必应）
- 使用智谱AI进行内容总结
- 支持动态页面爬取
- 完整的错误处理机制

## 安装说明

1. 安装依赖：
bash
pip install selenium beautifulsoup4 zhipuai

2. 安装 Chrome 和 ChromeDriver：

CentOS/RHEL:bash
yum install chromium chromium-headless chromedriver

Ubuntu/Debian:
bash
apt-get install chromium-browser chromium-chromedriver

3. 配置：
- 将插件目录复制到 chatgpt-on-wechat/plugins/ 下
- 在 config.py 中配置您的智谱AI API密钥

## 使用方法

- 搜索：搜索 关键词
- 知乎：知乎 问题
- 必应：必应 内容

## 示例
搜索 最新AI技术
知乎 ChatGPT的发展
必应 人工智能新闻
## 许可证

MIT License