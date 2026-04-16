"""FTP transport for file delivery."""

from __future__ import annotations

import ftplib
import io
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message

from .base import TransportProtocol


class FTPTransport(TransportProtocol):
    """Send messages/files via FTP."""

    name = "ftp"

    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message content or media via FTP."""
        host = config.get("host")
        if not host:
            return False

        port = config.get("port", 21)
        username = config.get("username", "anonymous")
        password = config.get("password", "")
        remote_path = config.get("path", "/")
        filename_template = config.get("filename", "{msg_id}.txt")
        passive = config.get("passive", True)

        try:
            with ftplib.FTP() as ftp:
                ftp.connect(host, port)
                ftp.login(username, password)
                ftp.cwd(remote_path)

                if msg.media:
                    for media in msg.media:
                        filename = self._get_filename(media, filename_template, msg.id)
                        if media._data:
                            ftp.storbinary(f"STOR {filename}", io.BytesIO(media._data))
                        elif media.full_url:
                            import urllib.request
                            with urllib.request.urlopen(media.full_url) as resp:
                                ftp.storbinary(f"STOR {filename}", resp)
                else:
                    filename = filename_template.format(
                        msg_id=msg.id, sender=msg.sender.platform_id
                    )
                    content = (msg.text or "").encode("utf-8")
                    ftp.storbinary(f"STOR {filename}", io.BytesIO(content))

                return True
        except Exception:
            return False

    def _get_filename(
        self, media: Any, template: str, msg_id: str
    ) -> str:
        filename = media.filename
        if not filename:
            ext = getattr(media, "mime_type", "bin")
            if "/" in ext:
                ext = ext.split("/")[1]
            filename = f"{msg_id}.{ext}"
        return template.format(
            msg_id=msg_id, filename=filename, sender=media.media_id
        )


class SFTPTransport(TransportProtocol):
    """Send messages/files via SFTP (requires paramiko)."""

    name = "sftp"

    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message content or media via SFTP."""
        try:
            import paramiko
        except ImportError:
            return False

        host = config.get("host")
        if not host:
            return False

        port = config.get("port", 22)
        username = config.get("username")
        password = config.get("password")
        key_file = config.get("key_file")
        remote_path = config.get("path", "/")
        filename_template = config.get("filename", "{msg_id}.txt")

        try:
            transport = paramiko.Transport((host, port))

            if key_file:
                private_key = paramiko.RSAKey.from_private_key_file(key_file)
                transport.connect(username=username, pkey=private_key)
            else:
                transport.connect(username=username, password=password)

            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.chdir(remote_path)

            if msg.media:
                for media in msg.media:
                    filename = self._get_filename(media, filename_template, msg.id)
                    if media._data:
                        sftp.putfo(io.BytesIO(media._data), filename)
                    elif media.full_url:
                        import urllib.request

                        with urllib.request.urlopen(media.full_url) as resp:
                            sftp.putfo(resp, filename)
            else:
                filename = filename_template.format(
                    msg_id=msg.id, sender=msg.sender.platform_id
                )
                content = (msg.text or "").encode("utf-8")
                sftp.putfo(io.BytesIO(content), filename)

            sftp.close()
            transport.close()
            return True
        except Exception:
            return False

    def _get_filename(
        self, media: Any, template: str, msg_id: str
    ) -> str:
        filename = media.filename
        if not filename:
            ext = getattr(media, "mime_type", "bin")
            if "/" in ext:
                ext = ext.split("/")[1]
            filename = f"{msg_id}.{ext}"
        return template.format(
            msg_id=msg_id, filename=filename, sender=media.media_id
        )
