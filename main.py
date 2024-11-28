from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from plugins import Plugin
import plugins
from .config import API_CONFIG
import zhipuai
from common.log import logger
from plugins import *
import requests
from bs4 import BeautifulSoup
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote
import time
import json

@plugins.register(
    name="ZhipuSearch",
    desire_priority=88,
    hidden=False,
    desc="智谱AI联网搜索",
    version="0.1",
    author="vision",
)
class ZhipuSearch(Plugin):
    def __init__(self):
        super().__init__()
        try:
            self.conf = super().load_config()
            if not self.conf:
                logger.warn("[ZhipuSearch] inited but api_key not found in config")
                self.api_key = None
            else:
                logger.info("[ZhipuSearch] inited and api_key loaded successfully")
                self.api_key = self.conf.get("api_key", API_CONFIG["api_key"])
            
            # 初始化 Selenium
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            logger.info("[ZhipuSearch] inited")
        except Exception as e:
            raise self.handle_error(e, "[ZhipuSearch] init failed, ignore ")

    def get_help_text(self, verbose=False, **kwargs):
        help_text = "智谱AI联网搜索使用说明：\n"
        help_text += "1. 发送'搜索 关键词'进行搜索\n"
        help_text += "2. 发送'知乎 问题'搜索知乎内容\n"
        help_text += "3. 发送'必应 内容'搜索必应\n"
        help_text += "\n示例：搜索 最新AI技术"
        return help_text

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [ContextType.TEXT]:
            return
            
        content = e_context["context"].content.strip()
        logger.debug("[ZhipuSearch] on_handle_context. content: %s" % content)

        # 定义关键词触发规则
        triggers = {
            "搜索": r"^搜索\s+(.+)$",
            "知乎": r"^知乎\s+(.+)$",
            "必应": r"^必应\s+(.+)$",
            "帮助": r"^(搜索|知乎|必应)\s*帮助$"
        }

        # 检查是否是帮助命令
        for trigger, pattern in triggers.items():
            if trigger == "帮助" and re.match(pattern, content):
                reply = Reply()
                reply.type = ReplyType.TEXT
                reply.content = self.get_help_text()
                e_context['reply'] = reply
                e_context.action = EventAction.BREAK_PASS
                return

        # 检查是否匹配任何触发规则
        matched = False
        query = None
        search_type = None
        for trigger, pattern in triggers.items():
            if trigger != "帮助":
                match = re.match(pattern, content)
                if match:
                    matched = True
                    query = match.group(1)
                    search_type = trigger
                    break

        if not matched:
            return

        try:
            # 根据不同的搜索类型调用不同的搜索方法
            if search_type == "知乎":
                result = self.search_zhihu(query)
            elif search_type == "必应":
                result = self.search_bing(query)
            else:
                result = self.search_all(query)

            # 使用智谱AI总结结果
            summary = self.summarize_with_zhipu(query, result)
            
            reply = Reply()
            reply.type = ReplyType.TEXT
            reply.content = summary
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
        except Exception as e:
            logger.error(f"[ZhipuSearch] error: {str(e)}")
            reply = Reply()
            reply.type = ReplyType.TEXT
            reply.content = "搜索过程出现错误，请稍后再试"
            e_context["reply"] = reply
            e_context.action = EventAction.CONTINUE

    def search_zhihu(self, query: str) -> list:
        """搜索知乎内容"""
        url = f"https://www.zhihu.com/search?q={quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
        }
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.text, 'html.parser')
            item_list = soup.find_all(class_='List-item')
            results = []
            for items in item_list:
                item_prelist = items.find(class_="RichText ztext CopyrightRichText-richText css-1g0fqss")
                if item_prelist:
                    item_text = re.sub(r'(<[^>]+>|\s)', '', str(item_prelist))
                    results.append(item_text)
            return results
        except Exception as e:
            logger.error(f"[ZhipuSearch] Zhihu search error: {str(e)}")
            return []

    def search_bing(self, query: str) -> list:
        """搜索必应内容"""
        try:
            self.driver.get(quote(f"https://cn.bing.com/search?q={query}", safe='=.'))
            for i in range(0, 2000, 350):  # 减少滚动次数以提高速度
                time.sleep(0.1)
                self.driver.execute_script('window.scrollTo(0, %s)' % i)
            
            html = self.driver.execute_script("return document.documentElement.outerHTML")
            soup = BeautifulSoup(html, 'html.parser')
            
            results = []
            # 搜索普通结果
            for item in soup.find_all(class_='b_algo'):
                title_elem = item.find('h2')
                if title_elem:
                    title = re.sub(r'(<[^>]+>|\s)', '', str(title_elem))
                    href = title_elem.find("a", href=True)
                    if href:
                        results.append({
                            'title': title,
                            'url': href["href"]
                        })
            
            # 搜索新闻结果
            for item in soup.find_all(class_='ans_nws ans_nws_fdbk'):
                for i in range(1, 5):  # 减少新闻数量以提高速度
                    news_item = item.find(class_=f"nws_cwrp nws_itm_cjk item{i}", url=True, titletext=True)
                    if news_item:
                        results.append({
                            'title': news_item["titletext"],
                            'url': news_item["url"].replace('\ue000', '').replace('\ue001', '')
                        })
            
            return results
        except Exception as e:
            logger.error(f"[ZhipuSearch] Bing search error: {str(e)}")
            return []

    def search_all(self, query: str) -> dict:
        """综合搜索"""
        results = {
            'bing': self.search_bing(query),
            'zhihu': self.search_zhihu(query)
        }
        return results

    def summarize_with_zhipu(self, query: str, search_results: dict) -> str:
        """使用智谱AI总结搜索结果"""
        try:
            # 格式化搜索结果
            formatted_results = "搜索结果：\n"
            if isinstance(search_results, dict):
                for source, results in search_results.items():
                    formatted_results += f"\n{source.upper()}来源：\n"
                    for result in results[:3]:  # 只取前3条结果
                        if isinstance(result, dict):
                            formatted_results += f"- {result['title']}\n"
                        else:
                            formatted_results += f"- {result}\n"
            else:
                for result in search_results[:3]:
                    formatted_results += f"- {result}\n"

            # 调用智谱AI进行总结
            client = zhipuai.ZhipuAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=API_CONFIG["model"],
                messages=[
                    {"role": "system", "content": "你是一个专业的搜索结果分析师，需要对搜索结果进行准确、客观的总结。"},
                    {"role": "user", "content": f"用户查询：{query}\n\n{formatted_results}\n\n请总结以上搜索结果的主要信息，并给出重点内容。"}
                ]
            )
            
            if hasattr(response.choices[0].message, 'content'):
                return response.choices[0].message.content
            else:
                return "无法总结搜索结果，请稍后再试"
        except Exception as e:
            logger.error(f"[ZhipuSearch] Summarize error: {str(e)}")
            return f"总结服务暂时无法使用: {str(e)}"

    def handle_error(self, e, message):
        """统一错误处理"""
        logger.error(f"{message}，错误信息：{e}")
        return message

    def __del__(self):
        """清理资源"""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
        except:
            pass