# NekroAgent 安全Shell执行插件

> 一个专为NekroAgent设计的安全Shell命令执行插件，可以安全地执行shell命令并将执行结果以图片形式返回。

## ✨ 功能特点

- 🔒 **安全执行**：在受控环境中安全执行shell命令
- 🖼️ **图片输出**：将命令执行结果转换为图片格式，便于查看和分享
- ⚡ **异步处理**：支持异步命令执行，不阻塞AI代理运行
- 🛡️ **权限控制**：内置安全检查机制，防止恶意命令执行
- 📊 **结果可视化**：将文本输出转换为清晰的图片格式

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 poetry 包管理工具
pip install poetry

# 设置虚拟环境目录在项目下
poetry config virtualenvs.in-project true

# 安装所有依赖
poetry install
```

### 2. 配置插件

在NekroAgent中启用此插件后，您可以配置以下参数：

- **最大执行时间**：设置命令执行的超时时间
- **图片尺寸**：配置输出图片的尺寸
- **字体设置**：自定义输出图片的字体样式
- **安全级别**：配置命令执行的安全级别

## 📖 使用方法

### 基本用法

在与NekroAgent的对话中，您可以这样使用：

```
请帮我执行 "ls -la" 命令
```

```
运行 "ps aux | grep python" 并显示结果
```

```
执行 "df -h" 查看磁盘使用情况
```

### 支持的命令类型

- 文件系统操作：`ls`, `pwd`, `find`, `du`, `df` 等
- 系统信息查询：`ps`, `top`, `free`, `uname` 等
- 网络工具：`ping`, `curl`, `wget` 等（在安全策略允许范围内）
- 文本处理：`grep`, `awk`, `sed`, `cat` 等

### 安全限制

为了确保系统安全，以下类型的命令会被限制或拒绝：

- ❌ 文件删除命令：`rm`, `rmdir`
- ❌ 系统修改命令：`sudo`, `chmod`, `chown`
- ❌ 网络服务命令：`nc`, `telnet`（某些情况下）
- ❌ 包管理命令：`apt`, `yum`, `pip install`

## ⚙️ 配置选项

### 基本配置

```python
# 命令执行超时时间（秒）
COMMAND_TIMEOUT = 30

# 输出图片最大宽度
IMAGE_MAX_WIDTH = 1200

# 输出图片最大高度
IMAGE_MAX_HEIGHT = 800

# 字体大小
FONT_SIZE = 12
```

### 安全配置

```python
# 允许的命令前缀
ALLOWED_COMMANDS = [
    "ls", "pwd", "ps", "top", "free", "df", "du",
    "cat", "grep", "find", "ping", "curl"
]

# 禁止的命令模式
FORBIDDEN_PATTERNS = [
    r"rm\s+", r"sudo\s+", r"chmod\s+", r"chown\s+"
]
```

## 🛠️ 开发指南

### 插件结构

```
nekro-plugin-sec-run/
├── __init__.py          # 插件主文件
├── pyproject.toml       # 项目配置
├── README.md           # 项目说明
└── assets/             # 资源文件
    └── fonts/          # 字体文件
```

### 核心功能

1. **命令安全检查**：在执行前验证命令的安全性
2. **异步执行**：使用asyncio执行shell命令
3. **结果处理**：将命令输出转换为结构化数据
4. **图片生成**：使用PIL生成包含结果的图片
5. **错误处理**：优雅处理各种执行错误

### 扩展开发

您可以通过以下方式扩展插件功能：

1. 添加新的安全命令到白名单
2. 自定义图片样式和布局
3. 增加命令执行的预处理和后处理逻辑
4. 集成更多的安全检查机制

## 📦 部署

### 本地测试

```bash
# 进入虚拟环境
poetry shell

# 运行测试
python -m pytest tests/
```

### 发布到NekroAI社区

1. 确保所有测试通过
2. 更新版本号在 `pyproject.toml` 中
3. 提交到GitHub仓库
4. 在NekroAI社区中发布插件

## 🔍 更多资源

- [NekroAgent 官方文档](https://doc.nekro.ai/)
- [插件开发详细指南](https://doc.nekro.ai/docs/04_plugin_dev/intro.html)
- [社区交流群](https://qm.qq.com/q/hJlRwD17Ae)：636925153
- [问题反馈](https://github.com/greenhandzdl/nekro-plugin-sec-run/issues)

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个插件！

### 贡献指南

1. Fork 这个仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- 感谢 [NekroAgent](https://nekro.ai/) 团队提供的优秀插件框架
- 感谢所有为这个项目做出贡献的开发者

---

<div align="center">
    <p>如果这个插件对您有帮助，请给我们一个⭐️！</p>
    <p>Made with ❤️ by greenhandzdl</p>
</div>
