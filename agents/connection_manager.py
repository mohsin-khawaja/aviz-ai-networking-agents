"""Connection manager for SSH/Telnet device identity verification.

This module provides optional SSH and Telnet connectivity for verifying device
identity and retrieving live device information.
"""
import os
import socket
from typing import Optional, Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Try to import paramiko for SSH
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    logger.warning("paramiko not available, SSH connections will be disabled")

# Try to import telnetlib (Python < 3.12) or telnetlib3 (Python 3.12+)
TELNET_AVAILABLE = False
TELNET_MODULE = None
try:
    import telnetlib
    TELNET_AVAILABLE = True
    TELNET_MODULE = telnetlib
    logger.debug("Using telnetlib (Python < 3.12)")
except ImportError:
    try:
        import telnetlib3
        TELNET_AVAILABLE = True
        TELNET_MODULE = telnetlib3
        logger.debug("Using telnetlib3 (Python 3.12+)")
    except ImportError:
        TELNET_AVAILABLE = False
        logger.warning("telnetlib not available (removed in Python 3.12+). Telnet features will be disabled.")
        logger.warning("To enable Telnet: pip install telnetlib3")


def run_ssh_command(
    host: str,
    username: str,
    password: str,
    command: str,
    timeout: int = 10,
    port: int = 22
) -> str:
    """
    Execute a command on a device via SSH using paramiko.
    
    Args:
        host: Device hostname or IP address
        username: SSH username
        password: SSH password
        command: Command to execute
        timeout: Connection timeout in seconds (default: 10)
        port: SSH port (default: 22)
        
    Returns:
        Command output as string
        
    Raises:
        Exception: If SSH connection or command execution fails
    """
    if not PARAMIKO_AVAILABLE:
        raise ImportError("paramiko not available, install with: pip install paramiko")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        logger.debug(f"Connecting to {host}:{port} via SSH")
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False
        )
        
        logger.debug(f"Executing command: {command}")
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        
        output = stdout.read().decode('utf-8', errors='ignore')
        error = stderr.read().decode('utf-8', errors='ignore')
        
        ssh.close()
        
        if error and "Permission denied" not in error.lower():
            logger.warning(f"SSH command stderr: {error}")
        
        return output.strip()
    
    except paramiko.AuthenticationException:
        logger.error(f"SSH authentication failed for {host}")
        raise Exception(f"SSH authentication failed for {host}")
    except paramiko.SSHException as e:
        logger.error(f"SSH error for {host}: {e}")
        raise Exception(f"SSH error: {str(e)}")
    except socket.timeout:
        logger.error(f"SSH connection timeout for {host}")
        raise Exception(f"SSH connection timeout for {host}")
    except Exception as e:
        logger.error(f"SSH connection error for {host}: {e}")
        raise Exception(f"SSH connection error: {str(e)}")


def run_telnet_command(
    host: str,
    username: str,
    password: str,
    command: str,
    timeout: int = 10,
    port: int = 23
) -> str:
    """
    Execute a command on a device via Telnet.
    
    Args:
        host: Device hostname or IP address
        username: Telnet username
        password: Telnet password
        command: Command to execute
        timeout: Connection timeout in seconds (default: 10)
        port: Telnet port (default: 23)
        
    Returns:
        Command output as string
        
    Raises:
        Exception: If Telnet connection or command execution fails
    """
    if not TELNET_AVAILABLE:
        raise ImportError("telnetlib not available. Install telnetlib3 for Python 3.12+: pip install telnetlib3")
    
    try:
        logger.debug(f"Connecting to {host}:{port} via Telnet")
        
        # Use telnetlib (Python < 3.12) or telnetlib3 (Python 3.12+)
        if TELNET_MODULE.__name__ == "telnetlib":
            # Standard telnetlib API
            tn = TELNET_MODULE.Telnet(host, port, timeout=timeout)
            
            # Read until login prompt
            tn.read_until(b"login:", timeout=timeout)
            tn.write(username.encode('ascii') + b"\n")
            
            # Read until password prompt
            tn.read_until(b"Password:", timeout=timeout)
            tn.write(password.encode('ascii') + b"\n")
            
            # Wait for command prompt (common patterns)
            prompt_patterns = [b">", b"#", b"$", b"%"]
            tn.read_until(prompt_patterns, timeout=timeout)
            
            # Execute command
            logger.debug(f"Executing command: {command}")
            tn.write(command.encode('ascii') + b"\n")
            
            # Read output until prompt appears again
            output = tn.read_until(prompt_patterns, timeout=timeout).decode('ascii', errors='ignore')
            
            tn.close()
        else:
            # telnetlib3 API (async, but we'll use it synchronously)
            import asyncio
            async def telnet_connect():
                try:
                    reader, writer = await TELNET_MODULE.open_connection(host, port)
                    # Read login prompt
                    data = await reader.readuntil(b"login:")
                    writer.write(username.encode('ascii') + b"\n")
                    await writer.drain()
                    
                    # Read password prompt
                    data = await reader.readuntil(b"Password:")
                    writer.write(password.encode('ascii') + b"\n")
                    await writer.drain()
                    
                    # Wait for prompt
                    prompt_patterns = [b">", b"#", b"$", b"%"]
                    data = await reader.readuntil(prompt_patterns)
                    
                    # Execute command
                    logger.debug(f"Executing command: {command}")
                    writer.write(command.encode('ascii') + b"\n")
                    await writer.drain()
                    
                    # Read output
                    output = await reader.readuntil(prompt_patterns)
                    output_text = output.decode('ascii', errors='ignore')
                    
                    writer.close()
                    await writer.wait_closed()
                    return output_text
                except Exception as e:
                    logger.error(f"Telnetlib3 connection error: {e}")
                    raise
            
            # Run async function
            try:
                output = asyncio.run(telnet_connect())
            except RuntimeError:
                # Handle case where event loop is already running
                import nest_asyncio
                try:
                    nest_asyncio.apply()
                    output = asyncio.run(telnet_connect())
                except ImportError:
                    # Fallback: create new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    output = loop.run_until_complete(telnet_connect())
                    loop.close()
        
        # Clean up output (remove command echo and prompt)
        lines = output.split('\n')
        # Remove first line (command echo) and last line (prompt)
        if len(lines) > 2:
            output = '\n'.join(lines[1:-1])
        
        return output.strip()
    
    except socket.timeout:
        logger.error(f"Telnet connection timeout for {host}")
        raise Exception(f"Telnet connection timeout for {host}")
    except ConnectionRefusedError:
        logger.error(f"Telnet connection refused for {host}")
        raise Exception(f"Telnet connection refused for {host}")
    except Exception as e:
        logger.error(f"Telnet connection error for {host}: {e}")
        raise Exception(f"Telnet connection error: {str(e)}")


def get_device_identity(device: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Verify device identity by connecting via SSH or Telnet.
    
    Tries SSH first, then Telnet, returning device identity information
    if credentials are available.
    
    Args:
        device: Device dictionary with name, ip, vendor, os, etc.
        
    Returns:
        Dictionary with identity information (hostname, vendor, os, etc.)
        or None if credentials not available or connection fails
    """
    ip = device.get("ip")
    if not ip:
        logger.debug(f"No IP address for device {device.get('name')}")
        return None
    
    # Get credentials from environment
    ssh_user = os.getenv("SSH_USER")
    ssh_pass = os.getenv("SSH_PASS")
    telnet_user = os.getenv("TELNET_USER")
    telnet_pass = os.getenv("TELNET_PASS")
    
    # Try SSH first if credentials available
    if ssh_user and ssh_pass:
        try:
            # Try common commands based on OS
            os_type = device.get("os", "").lower()
            if "sonic" in os_type or "linux" in os_type:
                command = "hostname && cat /etc/sonic/sonic_version.yml 2>/dev/null || echo 'SONiC device'"
            elif "nx-os" in os_type or "ios" in os_type or "iosxe" in os_type:
                command = "show version | head -20"
            else:
                command = "hostname"
            
            output = run_ssh_command(ip, ssh_user, ssh_pass, command)
            
            return {
                "method": "ssh",
                "hostname": output.split('\n')[0].strip() if output else "unknown",
                "raw_output": output,
                "success": True
            }
        except Exception as e:
            logger.debug(f"SSH identity check failed for {device.get('name')}: {e}")
    
    # Try Telnet if SSH failed or not available
    if telnet_user and telnet_pass:
        try:
            # Try common commands based on OS
            os_type = device.get("os", "").lower()
            if "sonic" in os_type or "linux" in os_type:
                command = "hostname"
            elif "nx-os" in os_type or "ios" in os_type or "iosxe" in os_type:
                command = "show version | head -20"
            else:
                command = "hostname"
            
            output = run_telnet_command(ip, telnet_user, telnet_pass, command)
            
            return {
                "method": "telnet",
                "hostname": output.split('\n')[0].strip() if output else "unknown",
                "raw_output": output,
                "success": True
            }
        except Exception as e:
            logger.debug(f"Telnet identity check failed for {device.get('name')}: {e}")
    
    return None

