"""NekroAgent 安全Shell执行插件

提供安全的shell命令执行功能。
执行命令并将结果以图片形式返回，确保执行环境的安全性。
"""

from typing import List

from nekro_agent.api.plugin import (
    ConfigBase,
    ExtraField,
    NekroPlugin,
    SandboxMethodType,
)from nekro_agent.core import logger
from nekro_agent.services.plugin.base import ConfigBase, NekroPlugin, SandboxMethodType
from pydantic import Field

from .utils.helper import execute_command_and_generate_image, send_image

# 插件元信息
plugin = NekroPlugin(
    name="安全Shell执行插件",
    module_name="sec_run",
    description="提供安全的shell命令执行功能，将执行结果以图片形式返回",
    version="1.0.0",
    author="greenhandzdl",
    url="https://github.com/greenhandzdl/nekro-plugin-sec-run",
)


# 插件配置
@plugin.mount_config()
class SecRunConfig(ConfigBase):
    """安全Shell执行配置"""

    COMMAND_TIMEOUT: int = Field(
        default=30,
        title="命令执行超时时间",
        description="shell命令执行的超时时间(秒)",
    )
    IMAGE_MAX_WIDTH: int = Field(
        default=1200,
        title="图片最大宽度",
        description="输出图片的最大宽度(像素)",
    )
    IMAGE_MAX_HEIGHT: int = Field(
        default=800,
        title="图片最大高度",
        description="输出图片的最大高度(像素)",
    )
    FONT_SIZE: int = Field(
        default=12,
        title="字体大小",
        description="图片中文本的字体大小",
    )
    FORBIDDEN_PATTERNS: List[str] = Field(
        default=[
            "rm ", "sudo ", "chmod ", "chown ", "mkfs", "fdisk",
            "dd if=", "kill ", "killall ", "reboot", "shutdown",
            "passwd ", "su ", "mount ", "umount ", "format"
        ],
        title="禁止命令模式",
        description="禁止执行的命令模式列表，支持部分匹配",
        json_schema_extra=ExtraField(sub_item_name="群组").model_dump(),
    )


# 获取配置实例
config: SecRunConfig = plugin.get_config(SecRunConfig)


@plugin.mount_sandbox_method(SandboxMethodType.AGENT, name="执行Shell命令", description="安全地执行shell命令并将结果以图片形式返回")
async def execute_shell_command(_ctx: AgentCtx, command: str) -> str:
    """安全地执行shell命令并将结果以图片形式返回。

    Args:
        command: 要执行的shell命令，例如 "ls -la", "ps aux", "df -h"。

    Returns:
        str: 生成的包含命令执行结果的图片文件路径。执行失败时返回错误图片。

    Raises:
        Exception: 命令执行时发生错误。

    Example:
        执行列目命令:
        execute_shell_command(command="ls -la")
        查看系统进程:
        execute_shell_command(command="ps aux | grep python")
        查看磁盘使用:
        execute_shell_command(command="df -h")
    """
    try:
        # 使用辅助函数执行命令并生成图片
        image_path = await execute_command_and_generate_image(
            command=command,
            ctx=_ctx,
            config=config,
            max_timeout=config.COMMAND_TIMEOUT
        )
        
        # 返回图片路径
        logger.info(f"已成功执行命令并生成图片: {command}")
        return image_path
        
    except Exception as e:
        logger.exception(f"执行shell命令时发生错误: {e}")
        # 在异常情况下，尝试创建错误图片
        try:
            from .utils.helper import _create_error_image
            return await _create_error_image(f"执行命令失败: {str(e)}", _ctx)
        except:
            return "执行命令失败且无法生成错误图片"


@plugin.mount_cleanup_method()
async def clean_up():
    """清理插件资源"""
    # 清理生成的临时图片文件
    logger.info("安全Shell执行插件资源已清理。")
