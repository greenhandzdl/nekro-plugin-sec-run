"""Shell Command to Image Plugin

This plugin provides a safe way for the Agent to execute shell commands and
return the combined prompt, command, and output (stdout + stderr) as a PNG
image. The image is encoded as a data URL, which can be displayed directly in
a web UI or chat client.

The plugin enforces a configurable execution timeout and blocks commands that
contain any of the patterns listed in the ``FORBIDDEN_PATTERNS`` configuration.
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
# Plugin instance
# ----------------------------------------------------------------------
plugin = NekroPlugin(
    name="Shell Command to Image",
    module_name="shell_to_image",
    description="Safely execute shell commands and return the output as an image.",
    version="0.1.0",
    author="greenhandzdl",
    url="https://github.com/greenhandzdl/convert_output_to_image",
)

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
@plugin.mount_config()
class SecRunConfig(ConfigBase):
    """Configuration for the Shell Command to Image plugin."""

    COMMAND_TIMEOUT: int = Field(
        default=30,
        title="Command Timeout (seconds)",
        description="Maximum time allowed for a command to run before being terminated.",
    )
    FONT_SIZE: int = Field(
        default=12,
        title="Font Size",
        description="Font size used when rendering the output text into an image.",
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
        ],
        title="Forbidden Command Patterns",
        description=(
            "List of substrings that are not allowed to appear in a command. "
            "The check is case‑insensitive and uses simple substring matching."
        ),
    )


# Retrieve the configuration instance
config = plugin.get_config(SecRunConfig)

# Prompt string used when rendering command input.
PROMPT = "~❯ "

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _contains_forbidden_pattern(command: str, patterns: List[str]) -> bool:
    """Return ``True`` if *command* contains any forbidden pattern.

    The check is performed case‑insensitively using simple substring matching.

    Args:
        command: The command string to inspect.
        patterns: A list of forbidden substrings.

    Returns:
        ``True`` if a forbidden pattern is found, otherwise ``False``.
    """
    lowered = command.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


async def _run_shell_command(command: str, timeout: int) -> Tuple[str, str]:
    """Execute *command* in a subprocess with a timeout.

    The command is executed via the system shell. Both ``stdout`` and ``stderr``
    are captured and returned as decoded strings.

    Args:
        command: Shell command to execute.
        timeout: Maximum number of seconds to allow the command to run.

    Returns:
        A tuple ``(stdout, stderr)`` where each element is a ``str``.

    Raises:
        asyncio.TimeoutError: If the command does not finish within *timeout*
            seconds.
        OSError: If the subprocess cannot be started.
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
        # Ensure the process is terminated if it exceeds the timeout.
        process.kill()
        await process.wait()
        raise
    stdout = stdout_bytes.decode(errors="replace") if stdout_bytes else ""
    stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
    return stdout, stderr


def _generate_image_data_url(text: str, font_size: int) -> str:
    """Render *text* into a PNG image and return a data URL.

    The image uses a white background and black monospaced text. If a monospaced
    TrueType font cannot be loaded, Pillow's default font is used.

    Args:
        text: Multiline text to render.
        font_size: Font size in points.

    Returns:
        A ``data:image/png;base64,...`` URL containing the generated image.
    """
    try:
        # Try to load a common monospaced font.
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        # Split text into lines while preserving empty lines.
        lines = text.splitlines() or [""]

        # Compute the required image size.
        max_line_width = max(font.getsize(line)[0] for line in lines)
        line_height = font.getsize("Ay")[1] + 4  # Small line spacing.
        padding = 10
        img_width = max_line_width + 2 * padding
        img_height = line_height * len(lines) + 2 * padding

        # Create the image.
        image = Image.new("RGB", (img_width, img_height), color="white")
        draw = ImageDraw.Draw(image)

        # Draw each line.
        y = padding
        for line in lines:
            draw.text((padding, y), line, font=font, fill="black")
            y += line_height

        # Encode the image to PNG in memory.
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        png_bytes = buffer.getvalue()
        base64_str = base64.b64encode(png_bytes).decode("ascii")
        return f"data:image/png;base64,{base64_str}"
    except Exception as exc:
        logger.error(f"Failed to generate image: {exc}")
        # Fallback: return a plain‑text data URL with the error message.
        error_msg = f"Image generation error: {exc}"
        encoded = base64.b64encode(error_msg.encode()).decode("ascii")
        return f"data:text/plain;base64,{encoded}"


# ----------------------------------------------------------------------
# Plugin method
# ----------------------------------------------------------------------
@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="执行Shell命令并返回图片",
    description="安全执行Shell命令并将输出（包括提示符）渲染为图片的data URL。",
)
async def run_command_to_pict(command: str, _ctx: AgentCtx) -> str:
    """Execute a shell command and return the result as a PNG image data URL.

    The function validates the command against a list of forbidden patterns,
    runs the command with a configurable timeout, captures both *stdout* and
    *stderr*, and finally renders the combined prompt, command, and output
    into an image.

    Args:
        command: Shell command to be executed.

    Returns:
        A ``data:image/png;base64,...`` URL that contains the rendered
        command prompt, the command itself, and its output.
    """
    # 1. Validate the command against forbidden patterns.
    try:
        if _contains_forbidden_pattern(command, config.FORBIDDEN_PATTERNS):
            warning_msg = "Command contains forbidden patterns and was blocked."
            logger.warning(f"Blocked forbidden command: {command}")
            return _generate_image_data_url(warning_msg, config.FONT_SIZE)
    except Exception as exc:
        logger.error(f"Error checking forbidden patterns: {exc}")
        return _generate_image_data_url(
            f"Error checking command: {exc}", config.FONT_SIZE
        )

    # 2. Execute the command.
    try:
        stdout, stderr = await _run_shell_command(command, config.COMMAND_TIMEOUT)
    except asyncio.TimeoutError:
        timeout_msg = f"Command timed out after {config.COMMAND_TIMEOUT} seconds."
        logger.error(f"Command timeout: {command}")
        return _generate_image_data_url(timeout_msg, config.FONT_SIZE)
    except OSError as exc:
        logger.error(f"OS error while executing command: {exc}")
        return _generate_image_data_url(f"OS error: {exc}", config.FONT_SIZE)
    except Exception as exc:
        logger.error(f"Unexpected error while executing command: {exc}")
        return _generate_image_data_url(f"Error: {exc}", config.FONT_SIZE)

    # 3. Combine prompt, command, and output.
    output_parts = [f"{PROMPT}{command}"]
    if stdout:
        output_parts.append(stdout.rstrip())
    if stderr:
        output_parts.append(stderr.rstrip())
    combined_text = "\n".join(output_parts)

    # 4. Generate image data URL.
    return _generate_image_data_url(combined_text, config.FONT_SIZE)
