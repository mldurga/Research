"""
Windows Service Wrapper
Allows the PI Notification service to run as a Windows service.
"""

import sys
import os
import time
import logging
from pathlib import Path

import win32serviceutil
import win32service
import win32event
import servicemanager

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from main import PINotificationService


class PINotificationWindowsService(win32serviceutil.ServiceFramework):
    """Windows service wrapper for PI Notification Service."""

    # Service configuration (can be overridden by config file)
    _svc_name_ = "PINotificationService"
    _svc_display_name_ = "PI Notification Email Processor"
    _svc_description_ = "Monitors Outlook emails and writes data to PI System using Ollama for extraction"

    def __init__(self, args):
        """Initialize the Windows service."""
        win32serviceutil.ServiceFramework.__init__(self, args)

        # Event to signal service stop
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

        # Service instance
        self.service = None

        # Setup logging to Windows Event Log
        self.setup_logging()

    def setup_logging(self):
        """Setup logging for Windows service."""
        try:
            # Create logs directory
            log_dir = Path(__file__).parent.parent / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)

            # Configure basic logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_dir / 'service.log'),
                    logging.StreamHandler()
                ]
            )

        except Exception as e:
            # Log to Windows Event Log
            servicemanager.LogErrorMsg(f"Failed to setup logging: {e}")

    def SvcStop(self):
        """Called when the service is requested to stop."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

        # Stop the service
        if self.service:
            self.service.stop()

        servicemanager.LogInfoMsg("PI Notification Service - Stopped")

    def SvcDoRun(self):
        """Called when the service is started."""
        try:
            servicemanager.LogInfoMsg("PI Notification Service - Starting")

            # Get config path
            config_path = self.get_config_path()

            # Create service instance
            self.service = PINotificationService(config_path)

            # Log service start
            servicemanager.LogInfoMsg("PI Notification Service - Started")

            # Run service in a separate thread
            import threading
            service_thread = threading.Thread(target=self.service.run)
            service_thread.daemon = True
            service_thread.start()

            # Wait for stop event
            while True:
                # Check if stop event is set
                rc = win32event.WaitForSingleObject(self.stop_event, 1000)
                if rc == win32event.WAIT_OBJECT_0:
                    break

            # Service is stopping
            servicemanager.LogInfoMsg("PI Notification Service - Shutting down")

        except Exception as e:
            servicemanager.LogErrorMsg(f"PI Notification Service - Error: {e}")
            self.SvcStop()

    def get_config_path(self):
        """
        Get configuration file path.

        Returns:
            Path to config file
        """
        # Try to get config path from environment variable
        config_path = os.environ.get('PI_NOTIFICATION_CONFIG')

        if not config_path:
            # Use default path
            project_root = Path(__file__).parent.parent
            config_path = project_root / 'config' / 'config.yaml'

        return str(config_path)


def install_service():
    """Install the Windows service."""
    try:
        print("Installing PI Notification Service...")
        win32serviceutil.HandleCommandLine(
            PINotificationWindowsService,
            argv=['', 'install']
        )
        print("Service installed successfully!")
        print("\nTo start the service, run:")
        print("  python windows_service.py start")
        print("\nOr use Windows Services Manager (services.msc)")

    except Exception as e:
        print(f"Error installing service: {e}")
        sys.exit(1)


def uninstall_service():
    """Uninstall the Windows service."""
    try:
        print("Uninstalling PI Notification Service...")
        win32serviceutil.HandleCommandLine(
            PINotificationWindowsService,
            argv=['', 'remove']
        )
        print("Service uninstalled successfully!")

    except Exception as e:
        print(f"Error uninstalling service: {e}")
        sys.exit(1)


def start_service():
    """Start the Windows service."""
    try:
        print("Starting PI Notification Service...")
        win32serviceutil.HandleCommandLine(
            PINotificationWindowsService,
            argv=['', 'start']
        )
        print("Service started successfully!")

    except Exception as e:
        print(f"Error starting service: {e}")
        sys.exit(1)


def stop_service():
    """Stop the Windows service."""
    try:
        print("Stopping PI Notification Service...")
        win32serviceutil.HandleCommandLine(
            PINotificationWindowsService,
            argv=['', 'stop']
        )
        print("Service stopped successfully!")

    except Exception as e:
        print(f"Error stopping service: {e}")
        sys.exit(1)


def restart_service():
    """Restart the Windows service."""
    try:
        print("Restarting PI Notification Service...")
        win32serviceutil.HandleCommandLine(
            PINotificationWindowsService,
            argv=['', 'restart']
        )
        print("Service restarted successfully!")

    except Exception as e:
        print(f"Error restarting service: {e}")
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        # No arguments - run as service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PINotificationWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Handle command line arguments
        command = sys.argv[1].lower()

        if command == 'install':
            install_service()
        elif command == 'remove' or command == 'uninstall':
            uninstall_service()
        elif command == 'start':
            start_service()
        elif command == 'stop':
            stop_service()
        elif command == 'restart':
            restart_service()
        else:
            # Let pywin32 handle standard service commands
            win32serviceutil.HandleCommandLine(PINotificationWindowsService)
