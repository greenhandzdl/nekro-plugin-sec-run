"""
安全Shell执行插件辅助函数模块

提供命令执行和图片生成功能
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont
from build import _ctx

from nekro_agent.api.schemas import AgentCtx
from nekro_agent.core import logger



async def execute_command_and_generate_image(
    command: str, config, max_timeout: int = 30
) -> str:
    """
    执行shell命令并将结果转换为图片

    Args:
        command: 要执行的shell命令
        config: 插件配置对象
        max_timeout: 命令执行超时时间(秒)

    Returns:
        str: 生成的图片文件路径

    Raises:
        Exception: 命令执行时发生错误
    """
    try:
        # 安全检查 - 防止执行危险命令（使用配置中的禁止模式）
        forbidden_patterns = config.FORBIDDEN_PATTERNS

        command_lower = command.lower().strip()
        for pattern in forbidden_patterns:
            if pattern in command_lower:
                logger.warning(f"检测到危险命令模式: {pattern}")
                return await _create_error_image(
                    f"安全检查失败: 命令包含危险操作 '{pattern}'"
                )

        # 获取当前提示符
        ps1 = os.environ.get('PS1', '$ ')
        if not ps1.endswith(' '):
            ps1 += ' '

        # 异步执行命令
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )

            # 等待命令完成或超时
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=max_timeout
            )

            # 解码输出
            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')

        except asyncio.TimeoutError:
            logger.warning(f"命令执行超时: {command}")
            return await _create_error_image(f"命令执行超时 ({max_timeout}秒)")
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return await _create_error_image(f"命令执行失败: {str(e)}")

        # 组合输出内容
        full_output = f"{ps1}{command}\n"
        if stdout_text:
            full_output += stdout_text
        if stderr_text:
            full_output += f"\n[错误输出]:\n{stderr_text}"
        if process.returncode != 0:
            full_output += f"\n[退出码]: {process.returncode}"

        # 生成图片
        image_path = await _create_command_output_image(full_output)
        logger.info(f"成功执行命令并生成图片: {command}")
        return image_path

    except Exception as e:
        logger.exception(f"执行命令时发生未知错误: {e}")
        return await _create_error_image(f"未知错误: {str(e)}")


async def send_image(image_path: str) -> str:
    """
    发送图片（这里返回图片路径，实际发送由调用方处理）

    Args:
        image_path: 图片文件路径

    Returns:
        str: 图片文件路径

    Raises:
        Exception: 发送图片时发生错误
    """
    try:
        if not Path(image_path).exists():
            logger.error(f"图片文件不存在: {image_path}")
            return await _create_error_image("图片文件不存在")

        logger.info(f"准备发送图片: {image_path}")
        return image_path

    except Exception as e:
        logger.exception(f"发送图片时发生错误: {e}")
        return await _create_error_image(f"发送图片失败: {str(e)}")


async def _create_command_output_image(output_text: str) -> str:
    """
    创建包含命令输出的图片

    Args:
        output_text: 要显示的文本内容

    Returns:
        str: 生成的图片文件路径

    Raises:
            Exception: 创建图片时发生错误
    """
    try:
        # 图片配置
        font_size = 12
        line_height = 16
        padding = 20
        max_width = 1200
        background_color = (40, 44, 52)  # 深色背景
        text_color = (171, 178, 191)     # 浅色文字
        prompt_color = (98, 175, 239)    # 提示符颜色

        # 尝试加载等宽字体
        try:
            # macOS 系统字体
            font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", font_size)
        except (OSError, IOError):
            try:
                # Linux 系统字体
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
            except (OSError, IOError):
                # 使用默认字体
                font = ImageFont.load_default()

        # 分割文本为行
        lines = output_text.split('\n')

        # 计算图片尺寸
        char_width = font_size * 0.6  # 等宽字体的近似字符宽度
        max_line_length = max(len(line) for line in lines) if lines else 1
        text_width = min(int(max_line_length * char_width), max_width - 2 * padding)
        text_height = len(lines) * line_height

        image_width = text_width + 2 * padding
        image_height = text_height + 2 * padding

        # 创建图片
        image = Image.new('RGB', (image_width, image_height), background_color)
        draw = ImageDraw.Draw(image)

        # 绘制文本
        y_offset = padding
        for i, line in enumerate(lines):
            # 第一行（命令行）使用特殊颜色
            if i == 0 and line.strip():
                # 分离提示符和命令
                if '$ ' in line:
                    prompt_part, command_part = line.split('$ ', 1)
                    prompt_part += '$ '

                    # 绘制提示符
                    draw.text((padding, y_offset), prompt_part, fill=prompt_color, font=font)
                    prompt_width = len(prompt_part) * char_width

                    # 绘制命令
                    draw.text((padding + prompt_width, y_offset), command_part, fill=(255, 255, 255), font=font)
                else:
                    draw.text((padding, y_offset), line, fill=(255, 255, 255), font=font)
            else:
                # 普通输出文本
                color = text_color
                if line.startswith('[错误输出]') or line.startswith('[退出码]'):
                    color = (231, 76, 60)  # 错误信息用红色

                draw.text((padding, y_offset), line, fill=color, font=font)

            y_offset += line_height

        # 保存图片
        output_path = _ctx.fs.shared_path / "command_output.png"
        image.save(output_path, "PNG")

        return str(output_path)

    except Exception as e:
        logger.exception(f"创建图片时发生错误: {e}")
        # 创建简单的错误图片
        return await _create_simple_error_image(f"图片生成失败: {str(e)}")


async def _create_error_image(error_message: str) -> str:
    """
    创建错误信息图片

    Args:
        error_message: 错误信息

    Returns:
        str: 生成的错误图片文件路径

    Raises:
        Exception: 创建图片时发生错误
    """
    try:
        return await _create_simple_error_image(error_message)
    except Exception as e:
        logger.exception(f"创建错误图片时发生错误: {e}")
        # 返回空路径作为最后的备选方案
        return ""


async def _create_simple_error_image(error_message: str) -> str:
    """
    创建简单的错误图片

    Args:
        error_message: 错误信息

    Returns:
        str: 生成的图片文件路径

    Raises:
        Exception: 创建图片时发生错误
    """
    # 简单的错误图片配置
    width, height = 600, 200
    background_color = (231, 76, 60)  # 红色背景
    text_color = (255, 255, 255)      # 白色文字

    # 创建图片
    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # 使用默认字体
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # 分割长文本
    words = error_message.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + " " + word if current_line else word
        # 简单的文本宽度估算
        if len(test_line) * 10 < width - 40:  # 预留边距
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    # 绘制文本
    total_text_height = len(lines) * 20
    start_y = (height - total_text_height) // 2

    for i, line in enumerate(lines):
        y_pos = start_y + i * 20
        draw.text((20, y_pos), line, fill=text_color, font=font)

    # 保存图片
    output_path = _ctx.fs.shared_path / "error_output.png"
    image.save(output_path, "PNG")

    return str(output_path)
