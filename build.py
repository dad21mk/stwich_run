"""
Build Script — Compile llm_cursor_tool.py into a standalone .exe
=================================================================

This script uses PyInstaller to package the LLM Cursor Automation Tool
into a single, portable executable file (.exe) for Windows.

Usage:
    python build.py

Prerequisites:
    - Python 3.10+ installed
    - PyInstaller installed: pip install pyinstaller
    - All dependencies from requiretmen.txt installed

Build Flags:
    --onefile    : Bundles everything into a single .exe
    --noconsole  : Hides the console window (runs silently in background)
    --name       : Sets the output filename to "LLM_Cursor_Tool.exe"
    --add-data   : Includes additional data files in the bundle

Output:
    dist/LLM_Cursor_Tool.exe   — The standalone executable

Notes:
    - The EXE should be run as Administrator for hotkey registration.
    - LM Studio must be running separately (it is NOT bundled in the EXE).
    - Build artifacts are created in 'build/' and 'dist/' directories.
    - The .spec file is auto-generated and can be customized for advanced builds.
"""

import subprocess
import sys
import os


def build():
    """
    Compile llm_cursor_tool.py into a standalone Windows executable.

    Steps:
        1. Locate the main script (llm_cursor_tool.py) in the same directory.
        2. Construct the PyInstaller command with appropriate flags.
        3. Run PyInstaller as a subprocess.
        4. Report success/failure and the output path.

    Raises:
        SystemExit: If the main script is not found or the build fails.
    """

    # --- Step 1: Locate the main script ---
    # Resolve the directory where this build script lives,
    # so it works regardless of the current working directory.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, "llm_cursor_tool.py")

    # Validate that the main script exists before attempting a build
    if not os.path.exists(main_script):
        print(f"ERROR: {main_script} not found!")
        print("       Make sure llm_cursor_tool.py is in the same folder as build.py.")
        sys.exit(1)

    # --- Step 2: Construct the PyInstaller command ---
    cmd = [
        sys.executable, "-m", "PyInstaller",  # Use the current Python interpreter
        "--onefile",                            # Bundle into a single .exe file
        "--noconsole",                          # No console window (background app)
        "--name", "LLM_Cursor_Tool",           # Output name: LLM_Cursor_Tool.exe
        "--add-data", f"{main_script};.",       # Include the script as data
        main_script,                            # Entry point script
    ]

    # --- Step 3: Run the build ---
    print("=" * 60)
    print("  Building LLM Cursor Tool EXE")
    print("=" * 60)
    print(f"  Source:  {main_script}")
    print(f"  Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=script_dir)

    # --- Step 4: Report results ---
    if result.returncode == 0:
        dist = os.path.join(script_dir, "dist", "LLM_Cursor_Tool.exe")
        print()
        print("=" * 60)
        print("  BUILD SUCCESSFUL!")
        print(f"  EXE location: {dist}")
        print()
        print("  To run: Right-click the EXE -> 'Run as administrator'")
        print("  (Admin is required for global hotkey registration)")
        print("=" * 60)
    else:
        print()
        print("  BUILD FAILED — see errors above.")
        print("  Common fixes:")
        print("    - pip install pyinstaller  (ensure it's installed)")
        print("    - Check for missing dependencies")
        sys.exit(1)


if __name__ == "__main__":
    build()
