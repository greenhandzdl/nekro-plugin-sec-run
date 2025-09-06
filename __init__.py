"""Shell命令转图片插件

该插件为插件提供了一种安全的方式来执行Shell命令，并将组合后的提示符、
命令和输出（stdout + stderr）作为PNG图片返回。图片被编码为data URL，
可以直接在Web UI或聊天客户端中显示。

该插件强制执行可配置的执行超时，并阻止包含在``FORBIDDEN_PATTERNS``
配置中列出的任何模式的命令。命令提示符也可以通过``PROMPT``配置字段进行配置。
"""

import asyncio
import base64
from io import BytesIO
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont
from pydantic import Field

from nekro_agent.api.schemas import AgentCtx
from nekro_agent.services.plugin.base import NekroPlugin, ConfigBase, SandboxMethodType
from nekro_agent.core import logger

# ----------------------------------------------------------------------
# 插件实例
# ----------------------------------------------------------------------
plugin = NekroPlugin(
    name="Shell命令转图片",
    module_name="nekro_plugin_sec_run",
    description="安全地执行Shell命令并将输出作为图片返回。",
    version="0.1.0",
    author="greenhandzdl",
    url="https://github.com/greenhandzdl/nekro-plugin-sec-run",
)

# ----------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------
@plugin.mount_config()
class SecRunConfig(ConfigBase):
    """Shell命令转图片插件的配置。

    所有运行时参数都可以通过这个类进行配置，包括在输出图片中渲染的命令提示符。
    """

    COMMAND_TIMEOUT: int = Field(
        default=30,
        title="命令超时（秒）",
        description="命令在被终止前允许运行的最长时间。",
    )
    FONT_SIZE: int = Field(
        default=12,
        title="字体大小",
        description="将输出文本渲染成图片时使用的字体大小。",
    )
    FORBIDDEN_PATTERNS: List[str] = Field(
        default_factory=lambda: [
            "rm ",
            "sudo ",
            "chmod ",
            "chown ",
            "mkfs",
            "fdisk",
            "dd if=",
            "kill ",
            "killall ",
            "reboot",
            "shutdown",
            "passwd ",
            "su ",
            "mount ",
            "umount ",
            "format",
            "wget",
            "curl",
        ],
        title="禁用的命令模式",
        description=(
            "不允许出现在命令中的子字符串列表，检查不区分大小写，并使用简单的子字符串匹配。"
        ),
    )
    PROMPT: str = Field(
        default="~❯ ",
        title="提示符",
        description="渲染命令输入时使用的提示符字符串。",
    )


# 获取配置实例
config = plugin.get_config(SecRunConfig)

# 提示符也作为从配置派生的顶级常量
PROMPT = config.PROMPT

# ----------------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------------
def _contains_forbidden_pattern(command: str, patterns: List[str]) -> bool:
    """检查 *command* 是否包含任何禁用的模式。

    检查不区分大小写，使用简单的子字符串匹配。

    Args:
        command: 要检查的命令字符串。
        patterns: 禁用子字符串的列表。

    Returns:
        如果找到禁用的模式，则返回 ``True``，否则返回 ``False``。
    """
    lowered = command.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


async def _run_shell_command(command: str, timeout: int) -> Tuple[str, str]:
    """在带有超时的子进程中执行 *command*。

    该命令通过系统shell执行。``stdout`` 和 ``stderr`` 都被捕获并作为解码后的字符串返回。

    Args:
        command: 要执行的Shell命令。
        timeout: 允许命令运行的最大秒数。

    Returns:
        一个元组 ``(stdout, stderr)``，其中每个元素都是 ``str``。

    Raises:
        asyncio.TimeoutError: 如果命令在 *timeout* 秒内未完成。
        OSError: 如果无法启动子进程。
    """
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        # 确保在超时后终止进程。
        process.kill()
        await process.wait()
        raise
    stdout = stdout_bytes.decode(errors="replace") if stdout_bytes else ""
    stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
    return stdout, stderr


def _generate_image_data_url(text: str, font_size: int) -> str:
    """将 *text* 渲染成PNG图片并返回一个data URL。

    图片使用白色背景和黑色等宽文本。如果无法加载等宽的TrueType字体，
    则使用Pillow的默认字体。

    Args:
        text: 要渲染的多行文本。
        font_size: 字体大小（磅）。

    Returns:
        一个包含生成图片的 ``data:image/png;base64,...`` URL。
    """
    try:
        # 尝试加载一个常见的等宽字体。
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        # 将文本分割成行，同时保留空行。
        lines = text.splitlines() or [""]

        # 计算所需的图像尺寸。
        ascent, descent = font.getmetrics()
        line_height = ascent + descent + 4  # 小行间距。
        max_line_width = max(font.getlength(line) for line in lines)
        padding = 10
        img_width = int(max_line_width) + 2 * padding
        img_height = line_height * len(lines) + 2 * padding

        # 创建图像。
        image = Image.new("RGB", (img_width, img_height), color="white")
        draw = ImageDraw.Draw(image)
        draw.text((padding, padding), text, font=font, fill="black")
        
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        png_bytes = buffer.getvalue()
        base64_str = base64.b64encode(png_bytes).decode("ascii")
        return f"data:image/png;base64,{base64_str}"
    except Exception as exc:
        logger.error(f"生成图片失败: {exc}")
        # 后备方案：返回带有错误消息的纯文本data URL。
        error_msg = f"图片生成错误: {exc}"
        encoded = base64.b64encode(error_msg.encode()).decode("ascii")
        return f"data:text/plain;base64,{encoded}"


# ----------------------------------------------------------------------
# 插件方法
# ----------------------------------------------------------------------
@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="执行Shell命令并返回图片",
    description="安全执行Shell命令并将输出（包括提示符）渲染为图片的data URL。",
)
async def run_command_to_pict(command: str, _ctx: AgentCtx) -> str:
    """执行一个Shell命令，并将结果作为PNG图片data URL返回。

    该函数根据禁用模式列表验证命令，使用可配置的超时运行命令，
    并捕获stdout和stderr。

    Args:
        command: 要执行的Shell命令。

    Returns:
        一个 ``data:image/png;base64,...`` URL，其中包含渲染的
        命令提示符、命令本身及其输出。

    Example:
        run_command_to_pict("ls -la")
    """
    # The framework seems to be passing arguments positionally, so we swap them.
    command, _ctx = _ctx, command

    # 1. 根据禁用模式验证命令。
    try:
        if not isinstance(command, str):
            err_msg = f"Invalid command type: {type(command)}"
            logger.error(err_msg)
            return _generate_image_data_url(err_msg, config.FONT_SIZE)
        if _contains_forbidden_pattern(command, config.FORBIDDEN_PATTERNS):
            warning_msg = "命令包含禁用模式，已被阻止。"
            logger.warning(f"已阻止禁用的命令: {command}")
            return _generate_image_data_url(warning_msg, config.FONT_SIZE)
    except Exception as exc:
        logger.error(f"检查禁用模式时出错: {exc}")
        return _generate_image_data_url(
            f"检查命令时出错: {exc}", config.FONT_SIZE
        )

    # 2. 执行命令。
    try:
        stdout, stderr = await _run_shell_command(command, config.COMMAND_TIMEOUT)
    except asyncio.TimeoutError:
        timeout_msg = f"命令在 {config.COMMAND_TIMEOUT} 秒后超时。"
        logger.error(f"命令超时: {command}")
        return _generate_image_data_url(timeout_msg, config.FONT_SIZE)
    except OSError as exc:
        logger.error(f"执行命令时发生操作系统错误: {exc}")
        return _generate_image_data_url(f"操作系统错误: {exc}", config.FONT_SIZE)
    except Exception as exc:
        logger.error(f"执行命令时发生意外错误: {exc}")
        return _generate_image_data_url(f"错误: {exc}", config.FONT_SIZE)

    # 3. 组合提示符、命令和输出。
    output_parts: List[str] = [f"{PROMPT}{command}"]
    if stdout:
        output_parts.append(stdout.rstrip())
    if stderr:
        output_parts.append(stderr.rstrip())
    combined_text = "\n".join(output_parts)

    # 4. 生成图片data URL。
    return _generate_image_data_url(combined_text, config.FONT_SIZE)


@plugin.mount_cleanup_method()
async def clean_up() -> None:
    """清理插件使用的资源。

    目前没有持久性资源，但提供此方法是为了将来的扩展（例如，关闭外部连接）。
    """
    logger.info("Shell命令转图片插件资源已清理")
