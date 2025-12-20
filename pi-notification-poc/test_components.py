"""
Component Testing Script
Tests individual components of the PI Notification POC
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config_loader import ConfigLoader


def setup_test_logger():
    """Setup a simple logger for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('TestRunner')


def test_config_loader():
    """Test configuration loading."""
    print("\n" + "="*60)
    print("Testing Configuration Loader")
    print("="*60)

    try:
        loader = ConfigLoader()
        config = loader.load()
        print("✓ Configuration loaded successfully")
        print(f"  - Email subject: {config['email']['target_subject']}")
        print(f"  - Ollama model: {config['ollama']['model']}")
        print(f"  - PI server: {config['pi']['server_name']}")
        return True
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return False


def test_ollama_connection():
    """Test Ollama service connection."""
    print("\n" + "="*60)
    print("Testing Ollama Connection")
    print("="*60)

    try:
        from ollama_client import OllamaClient

        loader = ConfigLoader()
        config = loader.load()
        logger = setup_test_logger()

        client = OllamaClient(config, logger)

        if client.check_connection():
            print("✓ Connected to Ollama service")

            # List models
            models = client.list_models()
            print(f"  - Available models: {', '.join(models)}")

            # Check configured model
            if client.validate_model_available():
                print(f"  - Configured model '{config['ollama']['model']}' is available")
            else:
                print(f"  - WARNING: Configured model '{config['ollama']['model']}' not found")

            # Test simple completion
            print("\n  Testing text extraction...")
            test_text = """
            Temperature Sensor A: 45.5°C
            Pressure Sensor B: 120.3 PSI
            """

            result = client.extract_data_from_text(test_text)
            if result:
                print(f"  ✓ Extraction successful: {len(result)} data points found")
                for item in result:
                    print(f"    - {item.get('tag_name', 'N/A')}: {item.get('value', 'N/A')}")
            else:
                print("  ✗ Extraction failed")

            return True
        else:
            print("✗ Cannot connect to Ollama service")
            print("  Make sure Ollama is running: http://localhost:11434")
            return False

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_pdf_parser():
    """Test PDF parsing capabilities."""
    print("\n" + "="*60)
    print("Testing PDF Parser")
    print("="*60)

    try:
        from pdf_parser import PDFParser

        loader = ConfigLoader()
        config = loader.load()
        logger = setup_test_logger()

        parser = PDFParser(config, logger)
        print("✓ PDF parser initialized successfully")

        # Check if PyPDF2 is working
        import PyPDF2
        print(f"  - PyPDF2 version: {PyPDF2.__version__}")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_outlook_connection():
    """Test Outlook connection."""
    print("\n" + "="*60)
    print("Testing Outlook Connection")
    print("="*60)

    try:
        from email_monitor import OutlookEmailMonitor

        loader = ConfigLoader()
        config = loader.load()
        logger = setup_test_logger()

        monitor = OutlookEmailMonitor(config, logger)

        if monitor.connect_to_outlook():
            print("✓ Connected to Outlook successfully")
            print(f"  - Inbox: {monitor.inbox.Name}")
            print(f"  - Monitoring for: '{config['email']['target_subject']}'")

            monitor.disconnect()
            return True
        else:
            print("✗ Failed to connect to Outlook")
            print("  Make sure Outlook is installed and configured")
            return False

    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("  Make sure pywin32 is installed")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_pi_connection():
    """Test PI System connection."""
    print("\n" + "="*60)
    print("Testing PI System Connection")
    print("="*60)

    try:
        from pi_writer import PIWriter

        loader = ConfigLoader()
        config = loader.load()
        logger = setup_test_logger()

        writer = PIWriter(config, logger)

        if writer.connect():
            print("✓ Connected to PI System")
            print(f"  - Server: {config['pi']['server_name']}")

            # Test write (simulation mode if PI not available)
            test_success = writer.write_value("TEST_TAG", 123.45)
            if test_success:
                print("  ✓ Test write successful")

            writer.disconnect()
            return True
        else:
            print("✗ Failed to connect to PI System")
            print("  This may be normal if running in simulation mode")
            return False

    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("  PIconnect requires PI SDK to be installed")
        print("  Running in simulation mode is OK for testing")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def main():
    """Run all component tests."""
    print("\n" + "="*60)
    print("PI Notification POC - Component Testing")
    print("="*60)

    results = {
        'Configuration': test_config_loader(),
        'PDF Parser': test_pdf_parser(),
        'Ollama': test_ollama_connection(),
        'Outlook': test_outlook_connection(),
        'PI System': test_pi_connection(),
    }

    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60)

    for component, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{component:20s}: {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print("\n" + "="*60)
    print(f"Total: {passed}/{total} tests passed")
    print("="*60)

    if passed == total:
        print("\n✓ All tests passed! System is ready.")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
