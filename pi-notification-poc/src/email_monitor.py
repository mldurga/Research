"""
Email Monitor Module
Monitors Outlook for emails with specific subject lines and processes attachments.
Designed for secure ADNOC environment with minimal dependencies.
"""

import os
import time
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import pythoncom
import win32com.client
from pathlib import Path


class OutlookEmailMonitor:
    """Monitor Outlook emails and process attachments."""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize the Outlook email monitor.

        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.outlook = None
        self.namespace = None
        self.inbox = None
        self.processed_folder = None

        # Email configuration
        self.target_subject = config['email']['target_subject'].lower()
        self.folder_name = config['email']['folder_name']
        self.check_interval = config['email']['check_interval']
        self.mark_as_read = config['email']['mark_as_read']
        self.processed_folder_name = config['email'].get('processed_folder')

        # PDF configuration
        self.temp_dir = Path(config['pdf']['temp_dir'])
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_mb = config['pdf']['max_size_mb']

    def connect_to_outlook(self) -> bool:
        """
        Connect to Outlook application.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Initialize COM
            pythoncom.CoInitialize()

            # Connect to Outlook
            self.logger.info("Connecting to Outlook...")
            self.outlook = win32com.client.Dispatch("Outlook.Application")
            self.namespace = self.outlook.GetNamespace("MAPI")

            # Get inbox folder
            self.inbox = self.namespace.GetDefaultFolder(6)  # 6 = Inbox
            self.logger.info(f"Connected to Outlook inbox: {self.inbox.Name}")

            # Setup processed folder if configured
            if self.processed_folder_name:
                self._setup_processed_folder()

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to Outlook: {e}")
            return False

    def _setup_processed_folder(self):
        """Create or get the processed emails folder."""
        try:
            # Try to find existing folder
            folders = self.inbox.Folders
            for folder in folders:
                if folder.Name == self.processed_folder_name:
                    self.processed_folder = folder
                    self.logger.info(f"Found existing folder: {self.processed_folder_name}")
                    return

            # Create new folder if not found
            self.processed_folder = self.inbox.Folders.Add(self.processed_folder_name)
            self.logger.info(f"Created new folder: {self.processed_folder_name}")

        except Exception as e:
            self.logger.warning(f"Could not setup processed folder: {e}")
            self.processed_folder = None

    def check_for_emails(self) -> List[Any]:
        """
        Check inbox for emails with target subject.

        Returns:
            List of email items matching the criteria
        """
        try:
            # Refresh inbox
            self.inbox = self.namespace.GetDefaultFolder(6)
            messages = self.inbox.Items
            messages.Sort("[ReceivedTime]", True)  # Sort by newest first

            matching_emails = []

            # Filter unread emails with target subject
            for message in messages:
                try:
                    # Check if email has the target subject
                    subject = str(message.Subject).lower()
                    if self.target_subject in subject:
                        # Only process unread emails
                        if not message.UnRead and not self.mark_as_read:
                            continue

                        matching_emails.append(message)
                        self.logger.info(f"Found matching email: {message.Subject}")

                except Exception as e:
                    self.logger.warning(f"Error checking email: {e}")
                    continue

            return matching_emails

        except Exception as e:
            self.logger.error(f"Error checking for emails: {e}")
            return []

    def extract_pdf_attachments(self, email) -> List[str]:
        """
        Extract PDF attachments from email to temp directory.

        Args:
            email: Outlook email object

        Returns:
            List of paths to extracted PDF files
        """
        pdf_paths = []

        try:
            attachments = email.Attachments

            if attachments.Count == 0:
                self.logger.warning(f"No attachments found in email: {email.Subject}")
                return pdf_paths

            for attachment in attachments:
                try:
                    filename = attachment.FileName

                    # Check if PDF
                    if not filename.lower().endswith('.pdf'):
                        self.logger.debug(f"Skipping non-PDF attachment: {filename}")
                        continue

                    # Check file size
                    size_mb = attachment.Size / (1024 * 1024)
                    if size_mb > self.max_size_mb:
                        self.logger.warning(f"PDF too large ({size_mb:.2f} MB): {filename}")
                        continue

                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = f"{timestamp}_{filename}"
                    pdf_path = self.temp_dir / safe_filename

                    # Save attachment
                    attachment.SaveAsFile(str(pdf_path))
                    pdf_paths.append(str(pdf_path))

                    self.logger.info(f"Extracted PDF: {filename} ({size_mb:.2f} MB)")

                except Exception as e:
                    self.logger.error(f"Error extracting attachment: {e}")
                    continue

            return pdf_paths

        except Exception as e:
            self.logger.error(f"Error processing attachments: {e}")
            return pdf_paths

    def mark_email_processed(self, email):
        """
        Mark email as processed (read and/or moved).

        Args:
            email: Outlook email object
        """
        try:
            # Mark as read
            if self.mark_as_read:
                email.UnRead = False
                self.logger.debug(f"Marked email as read: {email.Subject}")

            # Move to processed folder
            if self.processed_folder:
                email.Move(self.processed_folder)
                self.logger.info(f"Moved email to {self.processed_folder_name}")

        except Exception as e:
            self.logger.error(f"Error marking email as processed: {e}")

    def cleanup_temp_files(self, file_paths: List[str]):
        """
        Clean up temporary PDF files.

        Args:
            file_paths: List of file paths to delete
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.debug(f"Deleted temp file: {file_path}")
            except Exception as e:
                self.logger.warning(f"Could not delete temp file {file_path}: {e}")

    def get_email_metadata(self, email) -> Dict[str, Any]:
        """
        Extract metadata from email.

        Args:
            email: Outlook email object

        Returns:
            Dictionary with email metadata
        """
        try:
            return {
                'subject': str(email.Subject),
                'sender': str(email.SenderName),
                'sender_email': str(email.SenderEmailAddress) if hasattr(email, 'SenderEmailAddress') else '',
                'received_time': email.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S"),
                'body_preview': str(email.Body)[:200] if hasattr(email, 'Body') else ''
            }
        except Exception as e:
            self.logger.error(f"Error extracting email metadata: {e}")
            return {}

    def disconnect(self):
        """Disconnect from Outlook and cleanup."""
        try:
            self.outlook = None
            self.namespace = None
            self.inbox = None
            pythoncom.CoUninitialize()
            self.logger.info("Disconnected from Outlook")
        except Exception as e:
            self.logger.error(f"Error disconnecting from Outlook: {e}")
