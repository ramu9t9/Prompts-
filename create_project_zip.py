#!/usr/bin/env python3
"""
Project Zip Creator and Git Pusher for Angel One Options Analytics Tracker

This script creates a clean zip file of the project excluding unnecessary files
and pushes the project to GitHub repository.
"""

import os
import sys
import zipfile
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

class ProjectZipper:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.zip_name = f"angel_oi_tracker_clean_{self.timestamp}.zip"
        self.temp_dir = None
        
        # Files and folders to include
        self.include_patterns = [
            # Main application
            "angel_oi_tracker/*.py",
            "angel_oi_tracker/*.txt",
            "angel_oi_tracker/*.md",
            "angel_oi_tracker/.gitignore",
            "angel_oi_tracker/utils/*.py",
            "angel_oi_tracker/utils/*.json",
            "angel_oi_tracker/utils/__init__.py",
            
            # Documentation
            "docs/*.md",
            "docs/*.txt",
            
            # Tests (essential ones only)
            "tests/test_system.py",
            "tests/test_with_credentials.py",
            "tests/status_check.py",
            
            # Scripts (essential ones only)
            "scripts/mysql_setup.py",
            "scripts/migrate_to_mysql.py",
            "scripts/run_tracker.bat",
            "scripts/check_system.bat",
            "scripts/view_mysql_data.bat",
            
            # Root files
            "README.md",
            "requirements.txt"
        ]
        
        # Files and folders to exclude
        self.exclude_patterns = [
            # Python cache
            "**/__pycache__",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.pyd",
            
            # IDE files
            "**/.vscode",
            "**/.idea",
            "**/*.swp",
            "**/*.swo",
            "**/.DS_Store",
            "**/Thumbs.db",
            
            # Git
            "**/.git",
            "**/.gitignore",
            
            # Logs and temporary files
            "**/logs",
            "**/*.log",
            "**/*.tmp",
            "**/*.temp",
            
            # Database files
            "**/*.db",
            "**/*.sqlite",
            "**/*.sqlite3",
            
            # Data files
            "**/*.csv",
            "**/*.json",
            
            # Test files (exclude debug and excessive test files)
            "tests/debug_*.py",
            "tests/test_*.py",
            "tests/working_test.py",
            "tests/simple_test.py",
            
            # Script files (exclude legacy and setup files)
            "scripts/setup.py",
            "scripts/setup_*.py",
            "scripts/create_db.py",
            "scripts/check_db.py",
            "scripts/store_option_data.py",
            "scripts/view_data.py",
            "scripts/startup_backfill.py",
            "scripts/test_system.bat",
            "scripts/migrate_to_mysql.bat",
            "scripts/setup_mysql.bat",
            
            # Configuration files (exclude actual credentials)
            "angel_oi_tracker/angel_config.txt",
            
            # Temporary files
            "test_imports.py"
        ]
    
    def should_exclude(self, file_path):
        """Check if a file should be excluded"""
        file_path_str = str(file_path)
        
        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if pattern.startswith("**/"):
                # Glob pattern
                if file_path.match(pattern):
                    return True
            else:
                # Simple pattern
                if pattern in file_path_str:
                    return True
        
        return False
    
    def should_include(self, file_path):
        """Check if a file should be included"""
        file_path_str = str(file_path)
        
        # Check include patterns
        for pattern in self.include_patterns:
            if file_path.match(pattern):
                return True
        
        return False
    
    def create_clean_zip(self):
        """Create a clean zip file of the project"""
        print(f"📦 Creating clean zip file: {self.zip_name}")
        
        try:
            with zipfile.ZipFile(self.zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                files_added = 0
                
                # Walk through all files in the project
                for root, dirs, files in os.walk(self.project_root):
                    # Remove excluded directories from dirs list
                    dirs[:] = [d for d in dirs if not self.should_exclude(Path(root) / d)]
                    
                    for file in files:
                        file_path = Path(root) / file
                        relative_path = file_path.relative_to(self.project_root)
                        
                        # Skip if file should be excluded
                        if self.should_exclude(file_path):
                            continue
                        
                        # Include if it matches include patterns or is in essential directories
                        if (self.should_include(file_path) or 
                            str(relative_path).startswith(('angel_oi_tracker/', 'docs/', 'README.md'))):
                            
                            try:
                                zipf.write(file_path, relative_path)
                                files_added += 1
                                print(f"   ✅ Added: {relative_path}")
                            except Exception as e:
                                print(f"   ⚠️  Skipped {relative_path}: {e}")
                
                print(f"\n📊 Total files added: {files_added}")
        
        except Exception as e:
            print(f"❌ Error creating zip file: {e}")
            return False
        
        return True
    
    def check_git_status(self):
        """Check if git is initialized and has remote"""
        try:
            # Check if git is initialized
            result = subprocess.run(['git', 'status'], capture_output=True, text=True, cwd=self.project_root)
            if result.returncode != 0:
                print("❌ Git not initialized. Initializing git...")
                subprocess.run(['git', 'init'], cwd=self.project_root, check=True)
            
            # Check if remote exists
            result = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True, cwd=self.project_root)
            if 'origin' not in result.stdout:
                print("🔗 Adding remote origin...")
                subprocess.run([
                    'git', 'remote', 'add', 'origin', 
                    'https://github.com/ramu9t9/angel_oi_tracker.git'
                ], cwd=self.project_root, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Git setup error: {e}")
            return False
    
    def push_to_github(self):
        """Push the project to GitHub"""
        print("\n🚀 Pushing to GitHub...")
        
        try:
            # Check git status
            if not self.check_git_status():
                return False
            
            # Add all files
            print("📁 Adding files to git...")
            subprocess.run(['git', 'add', '.'], cwd=self.project_root, check=True)
            
            # Check if there are changes to commit
            result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, cwd=self.project_root)
            if not result.stdout.strip():
                print("ℹ️  No changes to commit")
                return True
            
            # Commit changes
            commit_message = f"Update Angel One Options Tracker - {self.timestamp}"
            print(f"💾 Committing changes: {commit_message}")
            subprocess.run(['git', 'commit', '-m', commit_message], cwd=self.project_root, check=True)
            
            # Push to GitHub
            print("⬆️  Pushing to GitHub...")
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=self.project_root, check=True)
            
            print("✅ Successfully pushed to GitHub!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Git push error: {e}")
            return False
    
    def create_gitignore(self):
        """Create a .gitignore file for the project"""
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Database
*.db
*.sqlite
*.sqlite3

# Data files
*.csv
options_snapshots.csv

# Configuration (contains sensitive data)
angel_config.txt

# Temporary files
*.tmp
*.temp
test_imports.py

# OS
.DS_Store
Thumbs.db
"""
        
        gitignore_path = self.project_root / '.gitignore'
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        
        print("📝 Created .gitignore file")
    
    def run(self):
        """Run the complete process"""
        print("🚀 Angel One Options Analytics Tracker - Project Zipper")
        print("=" * 60)
        
        # Create .gitignore
        self.create_gitignore()
        
        # Create clean zip
        print("\n📦 Step 1: Creating clean zip file...")
        if not self.create_clean_zip():
            print("❌ Failed to create zip file")
            return False
        
        print(f"✅ Zip file created: {self.zip_name}")
        
        # Push to GitHub
        print("\n🌐 Step 2: Pushing to GitHub...")
        if not self.push_to_github():
            print("❌ Failed to push to GitHub")
            return False
        
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! Project has been:")
        print(f"   📦 Zipped: {self.zip_name}")
        print("   🌐 Pushed to: https://github.com/ramu9t9/angel_oi_tracker")
        print("\n📋 Next steps:")
        print("   1. Share the zip file with others")
        print("   2. Check your GitHub repository")
        print("   3. Update documentation if needed")
        
        return True

def main():
    """Main function"""
    zipper = ProjectZipper()
    success = zipper.run()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 