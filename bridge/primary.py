#!/usr/bin/env python3
"""
Primary Node Manager for MySQL Cluster Bridge.

Manages the primary MySQL node running on the local machine.
Supports both systemctl-managed MySQL and binary installation.
"""

import os
import subprocess
import time
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
import logging

from .config import NodeConfig, NodeType, ClusterConfig

logger = logging.getLogger(__name__)


class PrimaryNodeManager:
    """
    Manages the primary MySQL node on the local machine.
    
    The primary node is where LineairDB storage engine runs.
    It can be managed via systemctl (system MySQL) or as a binary installation.
    """
    
    def __init__(self, config: ClusterConfig):
        """
        Initialize the Primary Node Manager.
        
        Args:
            config: Cluster configuration
        """
        self.config = config
        self.node_config = config.primary
        
        if not self.node_config:
            raise ValueError("Primary node configuration is required")
        
        # Determine MySQL binaries paths
        self._setup_paths()
    
    def _setup_paths(self):
        """Set up paths to MySQL binaries."""
        if self.config.mysqld_path:
            self.mysqld_path = self.config.mysqld_path
        elif self.config.mysql_bin_dir:
            self.mysqld_path = os.path.join(self.config.mysql_bin_dir, "mysqld")
        else:
            self.mysqld_path = shutil.which("mysqld") or "/usr/sbin/mysqld"
        
        if self.config.mysql_client_path:
            self.mysql_path = self.config.mysql_client_path
        elif self.config.mysql_bin_dir:
            self.mysql_path = os.path.join(self.config.mysql_bin_dir, "mysql")
        else:
            self.mysql_path = shutil.which("mysql") or "/usr/bin/mysql"
        
        if self.config.mysqlsh_path:
            self.mysqlsh_path = self.config.mysqlsh_path
        else:
            self.mysqlsh_path = shutil.which("mysqlsh") or "/usr/bin/mysqlsh"
    
    def check_mysql_installed(self) -> bool:
        """Check if MySQL is installed on the system."""
        if self.node_config.node_type == NodeType.LOCAL_SYSTEMCTL:
            result = subprocess.run(
                ["systemctl", "list-unit-files", "mysql.service"],
                capture_output=True,
                text=True
            )
            if "mysql.service" in result.stdout:
                return True
            # Also check for mysqld.service (CentOS/RHEL)
            result = subprocess.run(
                ["systemctl", "list-unit-files", "mysqld.service"],
                capture_output=True,
                text=True
            )
            return "mysqld.service" in result.stdout
        else:
            return os.path.exists(self.mysqld_path)
    
    def get_service_name(self) -> str:
        """Get the MySQL service name for systemctl."""
        # Check which service exists
        result = subprocess.run(
            ["systemctl", "list-unit-files", "mysql.service"],
            capture_output=True,
            text=True
        )
        if "mysql.service" in result.stdout:
            return "mysql"
        return "mysqld"
    
    def is_running(self) -> bool:
        """Check if MySQL is running."""
        if self.node_config.node_type == NodeType.LOCAL_SYSTEMCTL:
            service_name = self.get_service_name()
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True
            )
            return result.stdout.strip() == "active"
        else:
            # Check for binary installation - look for mysqld process
            result = subprocess.run(
                ["pgrep", "-f", "mysqld"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
    
    def start(self) -> Tuple[bool, str]:
        """
        Start the MySQL service.
        
        Returns:
            Tuple of (success, message)
        """
        if self.is_running():
            return True, "MySQL is already running"
        
        try:
            if self.node_config.node_type == NodeType.LOCAL_SYSTEMCTL:
                service_name = self.get_service_name()
                result = subprocess.run(
                    ["sudo", "systemctl", "start", service_name],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    return False, f"Failed to start MySQL: {result.stderr}"
            else:
                # Binary installation
                data_dir = self.node_config.data_dir or str(self.config.data_dir / "primary")
                config_file = self.node_config.config_file or str(self.config.config_dir / "primary.cnf")
                
                cmd = [
                    self.mysqld_path,
                    f"--datadir={data_dir}",
                    f"--defaults-file={config_file}",
                    "--user=mysql",
                    "&"
                ]
                subprocess.Popen(
                    " ".join(cmd),
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            # Wait for MySQL to be ready
            for _ in range(30):
                time.sleep(1)
                if self.is_running() and self.node_config.is_reachable():
                    return True, "MySQL started successfully"
            
            return False, "MySQL started but not responding"
        
        except subprocess.TimeoutExpired:
            return False, "Timeout starting MySQL"
        except Exception as e:
            return False, f"Error starting MySQL: {str(e)}"
    
    def stop(self) -> Tuple[bool, str]:
        """
        Stop the MySQL service.
        
        Returns:
            Tuple of (success, message)
        """
        if not self.is_running():
            return True, "MySQL is not running"
        
        try:
            if self.node_config.node_type == NodeType.LOCAL_SYSTEMCTL:
                service_name = self.get_service_name()
                result = subprocess.run(
                    ["sudo", "systemctl", "stop", service_name],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    return False, f"Failed to stop MySQL: {result.stderr}"
            else:
                # Binary installation - kill mysqld process
                result = subprocess.run(
                    ["pkill", "-f", "mysqld"],
                    capture_output=True,
                    text=True
                )
            
            # Wait for MySQL to stop
            for _ in range(30):
                time.sleep(1)
                if not self.is_running():
                    return True, "MySQL stopped successfully"
            
            return False, "MySQL still running after stop command"
        
        except subprocess.TimeoutExpired:
            return False, "Timeout stopping MySQL"
        except Exception as e:
            return False, f"Error stopping MySQL: {str(e)}"
    
    def restart(self) -> Tuple[bool, str]:
        """
        Restart the MySQL service.
        
        Returns:
            Tuple of (success, message)
        """
        if self.node_config.node_type == NodeType.LOCAL_SYSTEMCTL:
            try:
                service_name = self.get_service_name()
                result = subprocess.run(
                    ["sudo", "systemctl", "restart", service_name],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode != 0:
                    return False, f"Failed to restart MySQL: {result.stderr}"
                
                # Wait for MySQL to be ready
                for _ in range(30):
                    time.sleep(1)
                    if self.is_running() and self.node_config.is_reachable():
                        return True, "MySQL restarted successfully"
                
                return False, "MySQL restarted but not responding"
            
            except subprocess.TimeoutExpired:
                return False, "Timeout restarting MySQL"
            except Exception as e:
                return False, f"Error restarting MySQL: {str(e)}"
        else:
            # Binary installation - stop then start
            success, msg = self.stop()
            if not success:
                return False, f"Failed to stop: {msg}"
            return self.start()
    
    def get_status(self) -> dict:
        """
        Get the status of the MySQL service.
        
        Returns:
            Dictionary with status information
        """
        status = {
            "node_id": self.node_config.node_id,
            "hostname": self.node_config.hostname,
            "host": self.node_config.host,
            "port": self.node_config.port,
            "node_type": self.node_config.node_type.value,
            "running": self.is_running(),
            "reachable": self.node_config.is_reachable(),
        }
        
        if self.node_config.node_type == NodeType.LOCAL_SYSTEMCTL:
            service_name = self.get_service_name()
            result = subprocess.run(
                ["systemctl", "status", service_name],
                capture_output=True,
                text=True
            )
            status["service_status"] = result.stdout
        
        return status
    
    def execute_sql(self, sql: str) -> Tuple[bool, str]:
        """
        Execute SQL command on the primary node.
        
        Args:
            sql: SQL command to execute
            
        Returns:
            Tuple of (success, output/error)
        """
        try:
            cmd = [
                self.mysql_path,
                f"-h{self.node_config.host}",
                f"-P{self.node_config.port}",
                "-uroot",
                f"-p{self.node_config.mysql_root_password}",
                "-e", sql
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return False, result.stderr
            return True, result.stdout
        except Exception as e:
            return False, str(e)
    
    def execute_mysqlsh(self, script: str) -> Tuple[bool, str]:
        """
        Execute MySQL Shell script on the primary node.
        
        Args:
            script: JavaScript code to execute in MySQL Shell
            
        Returns:
            Tuple of (success, output/error)
        """
        try:
            uri = self.node_config.get_connection_uri()
            result = subprocess.run(
                [
                    self.mysqlsh_path,
                    uri,
                    "--js",
                    "--no-wizard",
                    "-e", script
                ],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return False, result.stderr
            return True, result.stdout
        except Exception as e:
            return False, str(e)
    
    def configure_for_group_replication(self) -> Tuple[bool, str]:
        """
        Configure the primary node for group replication.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            uri = self.node_config.get_connection_uri()
            script = f"""
print('Configuring primary instance for group replication...');
try {{
    dba.configureInstance('{uri}');
    print('Primary instance configured successfully');
}} catch(e) {{
    if (e.message.includes('already configured') || e.message.includes('already been configured')) {{
        print('Primary instance already configured');
    }} else {{
        print('Error: ' + e.message);
        throw e;
    }}
}}
"""
            return self.execute_mysqlsh(script)
        except Exception as e:
            return False, str(e)
    
    def create_cluster(self) -> Tuple[bool, str]:
        """
        Create the InnoDB cluster on the primary node.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            cluster_name = self.config.cluster_name
            local_address = self.node_config.get_local_address()
            
            script = f"""
shell.options.useWizards = false;
print('Creating or getting cluster...');
var cluster;
try {{
    cluster = dba.getCluster('{cluster_name}');
    print('Cluster already exists: ' + cluster.getName());
}} catch(e) {{
    if (e.message.includes('not found') || e.message.includes('does not exist') || e.message.includes('standalone instance')) {{
        print('Creating new cluster...');
        cluster = dba.createCluster('{cluster_name}', {{
            localAddress: '{local_address}'
        }});
        print('Cluster created: ' + cluster.getName());
    }} else {{
        throw e;
    }}
}}
print('Cluster status:');
print(JSON.stringify(cluster.status()));
"""
            return self.execute_mysqlsh(script)
        except Exception as e:
            return False, str(e)
    
    def get_cluster_status(self) -> Tuple[bool, str]:
        """
        Get the InnoDB cluster status.
        
        Returns:
            Tuple of (success, status_output)
        """
        try:
            cluster_name = self.config.cluster_name
            script = f"""
var cluster = dba.getCluster('{cluster_name}');
print(JSON.stringify(cluster.status(), null, 2));
"""
            return self.execute_mysqlsh(script)
        except Exception as e:
            return False, str(e)
    
    def generate_config_file(self) -> Path:
        """
        Generate MySQL configuration file for the primary node.
        
        Returns:
            Path to the generated configuration file
        """
        config_content = f"""[mysqld]
# Server Configuration
server-id = {self.node_config.server_id}
bind-address = 0.0.0.0
port = {self.node_config.port}

# Replication Configuration
log-bin = mysql-bin
binlog-format = ROW
gtid-mode = ON
enforce-gtid-consistency = ON
relay-log = mysql-relay-bin
relay-log-recovery = 1

# Group Replication Configuration
# Note: Group Replication settings will be configured via MySQL Shell

# Storage Engine Configuration
default-storage-engine = InnoDB

# Performance Tuning
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
max_connections = 200
max_allowed_packet = 256M

# LineairDB Support (if plugin is available)
# plugin-load-add = ha_lineairdb.so
"""
        
        config_path = self.config.config_dir / "primary.cnf"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w") as f:
            f.write(config_content)
        
        return config_path
    
    def check_lineairdb_plugin(self) -> Tuple[bool, str]:
        """
        Check if LineairDB storage engine plugin is available.
        
        Returns:
            Tuple of (available, message)
        """
        sql = "SHOW PLUGINS WHERE Name='lineairdb' OR Name='LINEAIRDB';"
        success, output = self.execute_sql(sql)
        
        if success and "lineairdb" in output.lower():
            return True, "LineairDB plugin is available"
        
        return False, "LineairDB plugin is not installed"
    
    def install_lineairdb_plugin(
        self,
        plugin_path: str,
        plugin_dir: str = "/usr/lib/mysql/plugin",
    ) -> Tuple[bool, str]:
        """
        Install the LineairDB storage engine plugin on the primary node.
        
        This function copies the plugin to the MySQL plugin directory
        and installs it.
        
        Args:
            plugin_path: Path to the LineairDB plugin shared library
            plugin_dir: MySQL plugin directory (default: /usr/lib/mysql/plugin)
            
        Returns:
            Tuple of (success, message)
        """
        if not os.path.exists(plugin_path):
            return False, f"Plugin file not found: {plugin_path}"
        
        plugin_filename = os.path.basename(plugin_path)
        target_path = os.path.join(plugin_dir, plugin_filename)
        
        try:
            # Copy plugin to MySQL plugin directory
            logger.info(f"Copying plugin to {target_path}...")
            
            # Try to copy directly first
            try:
                shutil.copy2(plugin_path, target_path)
            except PermissionError:
                # Try with sudo
                result = subprocess.run(
                    ["sudo", "cp", plugin_path, target_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    return False, f"Failed to copy plugin: {result.stderr}"
            
            # Set correct permissions
            try:
                os.chmod(target_path, 0o755)
            except PermissionError:
                subprocess.run(
                    ["sudo", "chmod", "755", target_path],
                    capture_output=True,
                    timeout=10
                )
            
            # Install the plugin
            sql = f"INSTALL PLUGIN lineairdb SONAME '{plugin_filename}';"
            success, output = self.execute_sql(sql)
            
            if not success:
                # Check if already installed
                if "already exists" in output.lower() or "duplicate" in output.lower():
                    return True, "LineairDB plugin already installed"
                return False, f"Failed to install plugin: {output}"
            
            return True, "LineairDB plugin installed successfully"
        
        except subprocess.TimeoutExpired:
            return False, "Timeout installing plugin"
        except Exception as e:
            return False, str(e)
    
    def get_plugin_dir(self) -> str:
        """
        Get the MySQL plugin directory.
        
        Returns:
            Path to the plugin directory
        """
        sql = "SHOW VARIABLES LIKE 'plugin_dir';"
        success, output = self.execute_sql(sql)
        
        if success:
            # Parse output to get plugin directory
            for line in output.split('\n'):
                if 'plugin_dir' in line.lower():
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[-1]
        
        # Default fallback
        return "/usr/lib/mysql/plugin"

