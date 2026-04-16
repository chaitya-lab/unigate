"""FTP transport plugin for file-based messaging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class FTPTransport:
    """Send messages by writing files via FTP."""
    
    name = "ftp"
    type = "transport"
    description = "FTP-based file transfer transport"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        from ftplib import FTP
        
        host = config.get("host")
        if not host:
            return False
        
        port = config.get("port", 21)
        username = config.get("username", "anonymous")
        password = config.get("password", "")
        remote_dir = config.get("remote_dir", "/")
        filename_pattern = config.get("filename", "{id}.json")
        
        payload = {
            "id": msg.id,
            "text": msg.text,
            "sender": {
                "id": msg.sender.platform_id,
                "name": msg.sender.name,
            },
            "session_id": msg.session_id,
        }
        
        if msg.media:
            payload["media"] = msg.media
        
        filename = filename_pattern.format(
            id=msg.id,
            session_id=msg.session_id,
            sender=msg.sender.platform_id,
        )
        
        content = json.dumps(payload, indent=2, default=str)
        
        try:
            ftp = FTP()
            ftp.connect(host, port)
            ftp.login(username, password)
            ftp.cwd(remote_dir)
            ftp.storbinary(f"STOR {filename}", __import__("io").BytesIO(content.encode()))
            ftp.quit()
            return True
        except Exception:
            return False


class SFTPTransport:
    """Send messages by writing files via SFTP (SSH File Transfer Protocol)."""
    
    name = "sftp"
    type = "transport"
    description = "SFTP-based secure file transfer transport"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        host = config.get("host")
        if not host:
            return False
        
        username = config.get("username")
        password = config.get("password")
        key_file = config.get("key_file")
        remote_dir = config.get("remote_dir", "/")
        filename_pattern = config.get("filename", "{id}.json")
        
        if not username:
            return False
        
        payload = {
            "id": msg.id,
            "text": msg.text,
            "sender": {
                "id": msg.sender.platform_id,
                "name": msg.sender.name,
            },
            "session_id": msg.session_id,
        }
        
        if msg.media:
            payload["media"] = msg.media
        
        filename = filename_pattern.format(
            id=msg.id,
            session_id=msg.session_id,
            sender=msg.sender.platform_id,
        )
        
        content = json.dumps(payload, indent=2, default=str)
        
        try:
            import paramiko
            
            transport = paramiko.Transport((host, 22))
            
            if key_file:
                from paramiko import RSAKey
                key = RSAKey.from_private_key_file(key_file)
                transport.connect(username=username, pkey=key)
            else:
                transport.connect(username=username, password=password)
            
            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.chdir(remote_dir)
            sftp.file(filename, "w").write(content)
            sftp.close()
            transport.close()
            return True
        except Exception:
            return False


class FileTransport:
    """Write messages to local filesystem."""
    
    name = "file"
    type = "transport"
    description = "Local filesystem transport"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        output_dir = config.get("directory")
        if not output_dir:
            return False
        
        filename_pattern = config.get("filename", "{id}.json")
        
        payload = {
            "id": msg.id,
            "text": msg.text,
            "sender": {
                "id": msg.sender.platform_id,
                "name": msg.sender.name,
            },
            "session_id": msg.session_id,
        }
        
        if msg.media:
            payload["media"] = msg.media
        
        filename = filename_pattern.format(
            id=msg.id,
            session_id=msg.session_id,
            sender=msg.sender.platform_id,
        )
        
        content = json.dumps(payload, indent=2, default=str)
        
        try:
            path = Path(output_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / filename).write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False
