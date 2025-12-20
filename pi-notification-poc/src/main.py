"""
PI Notification POC - Main Application
Orchestrates email monitoring, PDF parsing, Ollama extraction, and PI writing.
Designed for secure ADNOC environment.
"""

import os
import sys
import time
import logging
import signal
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Dict, Any

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import ConfigLoader
from email_monitor import OutlookEmailMonitor
from pdf_parser import PDFParser
from ollama_client import OllamaClient
from pi_writer import PIWriter


class PINotificationService:
    """Main service orchestrator."""

    def __init__(self, config_path: str = None):
        """
        Initialize the PI notification service.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()

        # Setup logging
        self.logger = self._setup_logging()

        # Initialize components
        self.email_monitor = None
        self.pdf_parser = None
        self.ollama_client = None
        self.pi_writer = None

        # Service state
        self.running = False
        self.consecutive_errors = 0
        self.max_consecutive_errors = self.config['error_handling']['max_consecutive_errors']

        self.logger.info("PI Notification Service initialized")

    def _setup_logging(self) -> logging.Logger:
        """
        Setup logging configuration.

        Returns:
            Configured logger instance
        """
        log_config = self.config['logging']

        # Create logger
        logger = logging.getLogger('PINotificationService')
        logger.setLevel(getattr(logging, log_config['level']))

        # Clear existing handlers
        logger.handlers = []

        # Create log directory
        log_file = Path(log_config['file_path'])
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_config['max_size_mb'] * 1024 * 1024,
            backupCount=log_config['backup_count']
        )
        file_handler.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_config['level']))

        # Formatter
        formatter = logging.Formatter(log_config['format'])
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        logger.addHandler(file_handler)
        if log_config.get('console_output', True):
            logger.addHandler(console_handler)

        return logger

    def initialize_components(self) -> bool:
        """
        Initialize all service components.

        Returns:
            True if all components initialized successfully
        """
        try:
            self.logger.info("Initializing service components...")

            # Initialize email monitor
            self.logger.info("Initializing email monitor...")
            self.email_monitor = OutlookEmailMonitor(self.config, self.logger)
            if not self.email_monitor.connect_to_outlook():
                self.logger.error("Failed to initialize email monitor")
                return False

            # Initialize PDF parser
            self.logger.info("Initializing PDF parser...")
            self.pdf_parser = PDFParser(self.config, self.logger)

            # Initialize Ollama client
            self.logger.info("Initializing Ollama client...")
            self.ollama_client = OllamaClient(self.config, self.logger)
            if not self.ollama_client.check_connection():
                self.logger.error("Failed to connect to Ollama service")
                return False

            if not self.ollama_client.validate_model_available():
                self.logger.warning("Configured model may not be available")

            # Initialize PI writer
            self.logger.info("Initializing PI writer...")
            self.pi_writer = PIWriter(self.config, self.logger)
            if not self.pi_writer.connect():
                self.logger.error("Failed to connect to PI server")
                return False

            self.logger.info("All components initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error initializing components: {e}")
            return False

    def process_email(self, email) -> bool:
        """
        Process a single email: extract PDFs, parse content, extract data, write to PI.

        Args:
            email: Outlook email object

        Returns:
            True if processing successful, False otherwise
        """
        try:
            # Get email metadata
            metadata = self.email_monitor.get_email_metadata(email)
            self.logger.info(f"Processing email: {metadata.get('subject', 'Unknown')}")

            # Extract PDF attachments
            pdf_paths = self.email_monitor.extract_pdf_attachments(email)

            if not pdf_paths:
                self.logger.warning("No PDF attachments found in email")
                self.email_monitor.mark_email_processed(email)
                return False

            all_success = True

            # Process each PDF
            for pdf_path in pdf_paths:
                try:
                    # Validate PDF
                    if not self.pdf_parser.validate_pdf(pdf_path):
                        self.logger.error(f"PDF validation failed: {pdf_path}")
                        continue

                    # Extract text from PDF
                    self.logger.info(f"Extracting text from PDF: {pdf_path}")
                    pdf_text = self.pdf_parser.extract_text_from_pdf(pdf_path)

                    if not pdf_text:
                        self.logger.warning(f"No text extracted from PDF: {pdf_path}")
                        continue

                    # Extract data using Ollama
                    self.logger.info("Processing text with Ollama...")
                    extracted_data = self.ollama_client.extract_data_from_text(pdf_text)

                    if not extracted_data:
                        self.logger.warning("No data extracted by Ollama")
                        continue

                    # Write to PI
                    self.logger.info(f"Writing {len(extracted_data)} data points to PI...")
                    write_results = self.pi_writer.write_multiple_values(extracted_data)

                    # Check if all writes were successful
                    failed_writes = [tag for tag, success in write_results.items() if not success]
                    if failed_writes:
                        self.logger.warning(f"Failed to write to tags: {failed_writes}")
                        all_success = False
                    else:
                        self.logger.info(f"Successfully wrote all data points to PI")

                except Exception as e:
                    self.logger.error(f"Error processing PDF {pdf_path}: {e}")
                    all_success = False

            # Cleanup temporary files
            self.email_monitor.cleanup_temp_files(pdf_paths)

            # Mark email as processed
            self.email_monitor.mark_email_processed(email)

            return all_success

        except Exception as e:
            self.logger.error(f"Error processing email: {e}")
            return False

    def run_once(self) -> bool:
        """
        Run one iteration of email checking and processing.

        Returns:
            True if iteration successful, False otherwise
        """
        try:
            self.logger.debug("Checking for new emails...")

            # Check for matching emails
            emails = self.email_monitor.check_for_emails()

            if not emails:
                self.logger.debug("No matching emails found")
                return True

            self.logger.info(f"Found {len(emails)} matching email(s)")

            # Process each email
            all_success = True
            for email in emails:
                success = self.process_email(email)
                if not success:
                    all_success = False

            # Reset error counter on success
            if all_success:
                self.consecutive_errors = 0
            else:
                self.consecutive_errors += 1

            return all_success

        except Exception as e:
            self.logger.error(f"Error in run iteration: {e}")
            self.consecutive_errors += 1
            return False

    def run(self):
        """Run the service main loop."""
        try:
            self.logger.info("Starting PI Notification Service...")

            # Initialize components
            if not self.initialize_components():
                self.logger.error("Failed to initialize components. Exiting.")
                return

            # Get check interval
            check_interval = self.config['email']['check_interval']
            self.running = True

            self.logger.info(f"Service started. Checking emails every {check_interval} seconds.")
            self.logger.info("Press Ctrl+C to stop the service.")

            # Main loop
            while self.running:
                # Check for max consecutive errors
                if self.consecutive_errors >= self.max_consecutive_errors:
                    self.logger.error(f"Maximum consecutive errors ({self.max_consecutive_errors}) reached. Stopping service.")
                    break

                # Run one iteration
                self.run_once()

                # Wait for next check
                time.sleep(check_interval)

        except KeyboardInterrupt:
            self.logger.info("Service stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error in service: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources before exit."""
        try:
            self.logger.info("Cleaning up resources...")

            if self.email_monitor:
                self.email_monitor.disconnect()

            if self.pi_writer:
                self.pi_writer.disconnect()

            self.logger.info("Cleanup complete")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def stop(self):
        """Stop the service."""
        self.logger.info("Stopping service...")
        self.running = False


def main():
    """Main entry point."""
    # Get config path from command line or use default
    config_path = sys.argv[1] if len(sys.argv) > 1 else None

    # Create and run service
    service = PINotificationService(config_path)

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\nReceived shutdown signal...")
        service.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run service
    service.run()


if __name__ == '__main__':
    main()
