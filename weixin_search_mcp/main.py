import sys
from typing import Annotated, Any, List, Dict, Optional
import asyncio
import time
import os
from fastmcp import FastMCP
from dotenv import load_dotenv

from pydantic import Field
import requests
from loguru import logger
from urllib.parse import urlparse, parse_qs
import argparse

# 导入工具函数
from weixin_search_mcp.tools.weixin_search import sogou_weixin_search, sogou_weixin_search_all, get_real_url, get_article_content

# 配置日志
def setup_logger(log_level="INFO"):
    """设置日志配置"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format= "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>"
    )

setup_logger(log_level="INFO")

parser = argparse.ArgumentParser()

parser.add_argument("--transport", type=str, default='http')
parser.add_argument("--port", type=int, default=8809)
parser.add_argument("--host", type=str, default='0.0.0.0')

args = parser.parse_args()

mcp = FastMCP("微信公众号内容获取")

@mcp.tool
def weixin_search(query: Annotated[str, "搜索关键词"], page: Annotated[int, "页码，默认1"] = 1) -> List[Dict[str, str]]:
    """在搜狗微信搜索中搜索指定关键词并返回单页结果
    Args:
        query: 搜索关键词
        page: 页码，默认1
    Returns:
        List[Dict[str, str]]: 搜索结果列表，包含 title, link, real_url, publish_time, page
    """
    return sogou_weixin_search(query, page=page)

@mcp.tool(output_schema=None)  # results contains list, can't use Dict[str, str]
def weixin_search_all(query: Annotated[str, "搜索关键词"], max_pages: Annotated[int, "最大页数，默认10"] = 10) -> Dict[str, Any]:
    """搜索所有页面的微信公众号文章（自动翻页）
    Args:
        query: 搜索关键词
        max_pages: 最大页数，默认10（每页约10条）
    Returns:
        Dict: 包含 total(总数), pages_fetched(实际页数), results(结果列表)
    """
    return sogou_weixin_search_all(query, max_pages=max_pages)

@mcp.tool
def get_weixin_article_content(real_url: Annotated[str, "真实微信公众号文章链接"], referer: Annotated[Optional[str], "请求来源,weixin_search的返回值"]) -> str:
    """获取微信公众号文章的正文内容
    Args:
        real_url: 真实微信公众号文章链接
        referer: 可选,请求来源,weixin_search的返回值
    Returns:
        str: 微信公众号文章的正文内容
    """
    return get_article_content(real_url, referer)

def app():
    host = args.host
    port = args.port
    transport = args.transport
    try:
        if transport == "http":
            mcp.run(host=host, port=port, transport=transport)
        elif transport == "stdio":
            mcp.run(transport=transport)
        else:
            raise ValueError("不支持的端口形式")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    app()