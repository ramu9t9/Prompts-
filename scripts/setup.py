#!/usr/bin/env python3
"""
Setup script for Angel One Options Analytics Tracker
"""

import os
import sys
import subprocess

def install_requirements():
    """Install required packages"""
    print("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False

def create_config_file():
    """Create configuration file if it doesn't exist"""
    config_file = "angel_config.txt"
    example_file = "angel_config.txt.example"
    
    if os.path.exists(config_file):
        print("✅ Configuration file already exists")
        return True
    
    if os.path.exists(example_file):
        print("📝 Creating configuration file from example...")
        try:
            with open(example_file, 'r') as src, open(config_file, 'w') as dst:
                dst.write(src.read())
            print("✅ Configuration file created. Please edit angel_config.txt with your credentials.")
            return True
        except Exception as e:
            print(f"❌ Failed to create config file: {e}")
            return False
    else:
        print("⚠️  Example config file not found. Please create angel_config.txt manually.")
        return False

def setup_database():
    """Setup the database"""
    print("🗄️  Setting up database...")
    try:
        from create_db import create_database
        create_database()
        print("✅ Database setup completed")
        return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Angel One Options Analytics Tracker - Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install requirements
    if not install_requirements():
        print("❌ Setup failed at requirements installation")
        sys.exit(1)
    
    # Create config file
    if not create_config_file():
        print("⚠️  Configuration file setup incomplete")
    
    # Setup database
    if not setup_database():
        print("❌ Setup failed at database creation")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit angel_config.txt with your Angel One credentials")
    print("2. Run: python test_system.py (to verify everything works)")
    print("3. Run: python startup_backfill.py (optional - for historical data)")
    print("4. Run: python main.py (to start real-time tracking)")
    print("\n📖 For more information, see README.md")

if __name__ == "__main__":
    main() 