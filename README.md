# 微信公众号内容搜索工具 (Weixin Search MCP)

这是一个基于MCP (Multimodal Capability Provider)的工具，用于搜索和获取微信公众号文章内容。通过搜狗微信搜索接口，可以方便地获取公众号文章并提取内容。

## 功能特点

- 通过关键词在搜狗微信搜索中查找公众号文章
- 自动获取文章的真实链接（从搜狗跳转链接转为微信原始链接）
- 提取文章的完整正文内容
- 支持批量获取多篇文章

## 安装方法

### 环境要求

- Python 3.12 或更高版本
- uv 包管理工具

### 安装步骤

使用 uv 创建虚拟环境并安装：

```bash
# 创建虚拟环境
uv venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或者在Windows上:
# .venv\Scripts\activate

# 安装项目
uv pip install -e .
```

## 使用方法

### 启动服务

启动HTTP服务器：

```bash
weixin_search_mcp --transport http --port 8809 --host 0.0.0.0
```

或者使用标准输入/输出模式（用于与其他应用集成）：

```bash
weixin_search_mcp --transport stdio
```

### 4. 配置MCP服务

有两种方式可以配置和启动MCP服务：

#### 方式一：使用stdio协议（直接连接）

在Claude配置中添加以下内容：

```json
{
    "mcpServers": {
        "weixin_search_mcp": {
            "command": "uvx",
            "args": ["weixin_search_mcp", "--transport", "stdio"]
        }
    }
}
```

#### 方式二：使用HTTP协议

1. 启动HTTP服务：

```sh
uvx weixin_search_mcp --transport http --port 8809
```

2. 在Claude配置中添加以下内容：

```json
{
    "mcpServers": {
        "weixin_search_mcp": {
            "type": "http",
            "url": "http://localhost:8809/mcp"
        }
    }
}
```

## 工具使用说明

本项目提供了以下工具来搜索和获取微信公众号内容：

### 微信搜索工具
- **weixin_search**: 在搜狗微信搜索中搜索指定关键词并返回结果列表
  - 参数: `query` - 搜索关键词
  - 返回: 包含标题、链接、真实URL和发布时间的文章列表

### 内容获取工具
- **get_weixin_article_content**: 获取微信公众号文章的正文内容
  - 参数: 
    - `real_url` - 真实微信公众号文章链接
    - `referer` - 可选，请求来源，通常为weixin_search返回的链接
  - 返回: 文章正文内容

### 使用示例

1. 搜索关键词相关的微信公众号文章:

```python
results = weixin_search("人工智能")
```

2. 获取文章内容:

```python
article_content = get_weixin_article_content(real_url="https://mp.weixin.qq.com/...", referer="https://weixin.sogou.com/...")
```

## 注意事项

- 该工具依赖于搜狗微信搜索接口，如果接口变更可能会影响工具功能
- 请合理控制请求频率，避免被搜狗或微信官方限制访问
- 获取的内容仅供学习研究使用，请遵守相关法律法规

## 许可证

MIT
