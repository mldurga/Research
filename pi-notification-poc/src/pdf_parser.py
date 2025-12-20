"""
PDF Parser Module
Extracts text content from PDF files using minimal dependencies.
Designed for secure ADNOC environment.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import PyPDF2


class PDFParser:
    """Parse PDF files and extract text content."""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize the PDF parser.

        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.extract_images = config['pdf'].get('extract_images', False)

    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """
        Extract all text from a PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text content or None if failed
        """
        try:
            if not Path(pdf_path).exists():
                self.logger.error(f"PDF file not found: {pdf_path}")
                return None

            self.logger.info(f"Parsing PDF: {pdf_path}")

            # Open PDF file
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                # Get number of pages
                num_pages = len(pdf_reader.pages)
                self.logger.debug(f"PDF has {num_pages} pages")

                # Extract text from all pages
                full_text = []

                for page_num in range(num_pages):
                    try:
                        page = pdf_reader.pages[page_num]
                        text = page.extract_text()

                        if text:
                            full_text.append(f"--- Page {page_num + 1} ---\n{text}")
                            self.logger.debug(f"Extracted {len(text)} characters from page {page_num + 1}")
                        else:
                            self.logger.warning(f"No text found on page {page_num + 1}")

                    except Exception as e:
                        self.logger.error(f"Error extracting text from page {page_num + 1}: {e}")
                        continue

                # Combine all pages
                combined_text = "\n\n".join(full_text)

                if not combined_text.strip():
                    self.logger.warning(f"No text extracted from PDF: {pdf_path}")
                    return None

                self.logger.info(f"Successfully extracted {len(combined_text)} characters from PDF")
                return combined_text

        except PyPDF2.errors.PdfReadError as e:
            self.logger.error(f"PDF read error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing PDF: {e}")
            return None

    def extract_metadata(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract metadata from PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with PDF metadata
        """
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                metadata = {
                    'num_pages': len(pdf_reader.pages),
                    'file_name': Path(pdf_path).name,
                    'file_size_kb': Path(pdf_path).stat().st_size / 1024
                }

                # Extract PDF metadata if available
                if pdf_reader.metadata:
                    pdf_meta = pdf_reader.metadata
                    metadata['title'] = pdf_meta.get('/Title', '')
                    metadata['author'] = pdf_meta.get('/Author', '')
                    metadata['subject'] = pdf_meta.get('/Subject', '')
                    metadata['creator'] = pdf_meta.get('/Creator', '')
                    metadata['producer'] = pdf_meta.get('/Producer', '')

                    # Try to get creation/modification dates
                    if '/CreationDate' in pdf_meta:
                        metadata['creation_date'] = str(pdf_meta['/CreationDate'])
                    if '/ModDate' in pdf_meta:
                        metadata['modification_date'] = str(pdf_meta['/ModDate'])

                self.logger.debug(f"Extracted metadata from PDF: {metadata}")
                return metadata

        except Exception as e:
            self.logger.error(f"Error extracting PDF metadata: {e}")
            return {'file_name': Path(pdf_path).name, 'error': str(e)}

    def validate_pdf(self, pdf_path: str) -> bool:
        """
        Validate that the file is a readable PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            True if valid PDF, False otherwise
        """
        try:
            if not Path(pdf_path).exists():
                self.logger.error(f"File does not exist: {pdf_path}")
                return False

            if not pdf_path.lower().endswith('.pdf'):
                self.logger.error(f"File is not a PDF: {pdf_path}")
                return False

            # Try to open and read the PDF
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)

                if num_pages == 0:
                    self.logger.error(f"PDF has no pages: {pdf_path}")
                    return False

            self.logger.debug(f"PDF validation passed: {pdf_path}")
            return True

        except Exception as e:
            self.logger.error(f"PDF validation failed: {e}")
            return False

    def extract_text_chunks(self, pdf_path: str, chunk_size: int = 4000) -> list:
        """
        Extract text from PDF in chunks for LLM processing.

        Args:
            pdf_path: Path to PDF file
            chunk_size: Maximum characters per chunk

        Returns:
            List of text chunks
        """
        try:
            full_text = self.extract_text_from_pdf(pdf_path)

            if not full_text:
                return []

            # Split text into chunks
            chunks = []
            current_chunk = ""

            for line in full_text.split('\n'):
                if len(current_chunk) + len(line) < chunk_size:
                    current_chunk += line + '\n'
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = line + '\n'

            # Add last chunk
            if current_chunk:
                chunks.append(current_chunk.strip())

            self.logger.info(f"Split PDF into {len(chunks)} chunks")
            return chunks

        except Exception as e:
            self.logger.error(f"Error creating text chunks: {e}")
            return []

    def clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing excessive whitespace and special characters.

        Args:
            text: Raw text from PDF

        Returns:
            Cleaned text
        """
        try:
            # Remove multiple newlines
            cleaned = '\n'.join(line.strip() for line in text.split('\n') if line.strip())

            # Remove excessive spaces
            cleaned = ' '.join(cleaned.split())

            return cleaned

        except Exception as e:
            self.logger.error(f"Error cleaning text: {e}")
            return text
