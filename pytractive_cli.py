#!/usr/bin/env python3
"""
Enhanced entry point for PyTractive CLI.

This script provides a robust entry point with comprehensive error handling,
environment validation, dependency checking, and helpful user guidance.
"""

import sys
import os
from pathlib import Path
import subprocess
import importlib

def print_banner():
    """Print the PyTractive banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                        PyTractive v2.0                        ║
    ║              Modern Tractive GPS Tracker Interface            ║
    ║                                                               ║
    ║  🐕 Pet GPS Tracking  🔋 Battery Monitoring  📊 Analytics    ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Error: PyTractive requires Python 3.8 or higher")
        print(f"   Current version: {sys.version_info.major}.{sys.version_info.minor}")
        print("   Please upgrade Python and try again.")
        sys.exit(1)

def check_dependencies():
    """Check if required dependencies are available."""
    required_deps = [
        ('click', 'click'),
        ('requests', 'requests'),
        ('pandas', 'pandas'),
        ('folium', 'folium'),
        ('geopy', 'geopy'),
        ('Pillow', 'PIL')
    ]
    
    missing_deps = []
    
    for dep_name, import_name in required_deps:
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing_deps.append(dep_name)
    
    if missing_deps:
        print("❌ Missing required dependencies:")
        for dep in missing_deps:
            print(f"   - {dep}")
        
        print("\n📦 Install missing dependencies with:")
        print(f"   pip install {' '.join(missing_deps)}")
        print("\n   Or install all dependencies with:")
        print("   pip install -r PyTractive/requirements.txt")
        
        return False
    
    return True

def setup_environment():
    """Setup environment and add PyTractive to path if running from source."""
    script_dir = Path(__file__).parent
    pytractive_dir = script_dir / "PyTractive"
    
    if pytractive_dir.exists():
        # Running from source
        sys.path.insert(0, str(script_dir))
        print("🔧 Running from source directory")
        return True
    else:
        # Check if installed package is available
        try:
            import PyTractive
            print("📦 Using installed PyTractive package")
            return True
        except ImportError:
            print("❌ Error: PyTractive package not found")
            print("\n📦 Please install PyTractive:")
            print("   pip install PyTractive")
            print("\n   Or if running from source:")
            print("   pip install -e .")
            return False

def check_configuration():
    """Check if basic configuration is available."""
    env_vars = ['TRACTIVE_EMAIL', 'TRACTIVE_PASSWORD', 'TRACTIVE_HOME_LAT', 'TRACTIVE_HOME_LON']
    missing_vars = [var for var in env_vars if not os.environ.get(var)]
    
    if missing_vars:
        print("⚙️  Configuration Notice:")
        print("   Some environment variables are not set:")
        for var in missing_vars:
            print(f"   - {var}")
        
        print("\n🔑 To get started, set your credentials:")
        print("   export TRACTIVE_EMAIL='your.email@example.com'")
        print("   export TRACTIVE_PASSWORD='your_password'")
        print("   export TRACTIVE_HOME_LAT='40.7128'")
        print("   export TRACTIVE_HOME_LON='-74.0060'")
        print("\n   Or create a config file in the current directory.")
        return False
    
    return True

def show_quick_help():
    """Show quick help when no arguments provided."""
    print("🚀 Quick Start:")
    print("   python pytractive_cli.py demo        # Show demonstration")
    print("   python pytractive_cli.py status      # Check tracker status")
    print("   python pytractive_cli.py location    # Get GPS location")
    print("   python pytractive_cli.py --help      # Full help")
    print()
    print("📚 Popular Commands:")
    print("   battery -d                           # Detailed battery info")
    print("   location -i                          # Location with map")
    print("   history --hours 12                   # 12-hour location history")
    print("   export -f my_data.csv                # Export GPS data")
    print("   monitor 100                          # Monitor distance from home")

def main():
    """Enhanced main entry point with comprehensive validation and error handling."""
    # Import exceptions early so they're available in except blocks
    ConfigurationError = None
    AuthenticationError = None
    
    try:
        # Check Python version first
        check_python_version()
        
        # Special case for version check
        if '--version' in sys.argv or '-V' in sys.argv:
            print("PyTractive v2.0.0")
            print("Modern Tractive GPS Tracker Interface")
            return
        
        # Special case for demo without dependencies
        if len(sys.argv) > 1 and sys.argv[1] == 'demo' and '--no-deps' in sys.argv:
            print_banner()
            show_quick_help()
            return
        
        # Setup environment
        if not setup_environment():
            sys.exit(1)
        
        # Check dependencies
        if not check_dependencies():
            sys.exit(1)
        
        # Now import PyTractive components
        try:
            from PyTractive.cli import cli
            from PyTractive.logging_config import setup_logging
            from PyTractive.exceptions import ConfigurationError, AuthenticationError
        except ImportError as e:
            print(f"❌ Error importing PyTractive components: {e}")
            sys.exit(1)
        
        # Show banner for interactive use
        if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['demo', 'help', '--help', '-h']):
            print_banner()
        
        # Handle no arguments case
        if len(sys.argv) == 1:
            show_quick_help()
            print("\n" + "="*60)
            cli.main(args=["--help"], standalone_mode=False)
            return
        
        # Handle help requests
        if sys.argv[1] in ['help', '--help', '-h']:
            cli.main(args=["--help"], standalone_mode=False)
            return
        
        # Setup logging
        verbose = '--verbose' in sys.argv or '-v' in sys.argv
        if verbose:
            setup_logging('DEBUG')
        else:
            setup_logging('INFO')
        
        # Check configuration for commands that need it
        commands_needing_config = [
            'status', 'location', 'control', 'pet', 'export', 'monitor', 
            'live_location', 'battery', 'share', 'home_status', 'info', 'history'
        ]
        
        if len(sys.argv) > 1 and sys.argv[1] in commands_needing_config:
            if not check_configuration():
                print("\n⚠️  You can still run 'demo' or 'stats' commands without configuration.")
                sys.exit(1)
        
        # Handle legacy arguments for backward compatibility
        legacy_args = {
            '--live', '--led', '--buzzer', '--battery_saver', '--public',
            '--trigger', '--gps', '--nloc', '--pet', '--export', '-I'
        }
        
        if any(arg in sys.argv for arg in legacy_args):
            print("🔄 [PyTractive] Detected legacy arguments. Routing to modern CLI...")
            print("   Consider using the new command format for better experience.")
        
        # Run the CLI
        cli()
        
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        # Handle PyTractive-specific errors if available
        if ConfigurationError and isinstance(e, ConfigurationError):
            print(f"\n❌ Configuration Error: {e}")
            print("\n💡 Tips:")
            print("   - Check your environment variables")
            print("   - Verify your config file")
            print("   - Run 'python pytractive_cli.py demo' for setup help")
            sys.exit(1)
        elif AuthenticationError and isinstance(e, AuthenticationError):
            print(f"\n❌ Authentication Error: {e}")
            print("\n🔑 Please check:")
            print("   - Your email and password are correct")
            print("   - Network connectivity")
            print("   - Tractive service status")
            sys.exit(1)
        else:
            print(f"\n💥 Unexpected error: {e}")
            print("\n🐛 Please report this issue with:")
            print("   - The command you ran")
            print("   - This error message")
            print("   - Your Python version")
            if '--verbose' not in sys.argv and '-v' not in sys.argv:
                print("\n🔍 For more details, run with --verbose flag")
            sys.exit(1)


if __name__ == "__main__":
    main()
