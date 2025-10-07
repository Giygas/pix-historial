#!/usr/bin/env python3
"""
Test runner script for the PIX Historial project.
Run this script to execute all tests with coverage reporting.
"""

import subprocess
import sys
import os


def run_command(command, description):
    """Run a command and handle the result"""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {description}:")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def main():
    """Main test runner function"""
    print("PIX Historial Test Suite")
    print("=" * 60)

    # Ensure we're in the project root
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Install test dependencies if needed
    print("Checking test dependencies...")
    test_deps = [
        "pytest>=8.3.4",
        "pytest-asyncio>=0.25.3",
        "pytest-cov>=6.0.0",
        "httpx>=0.28.1",
        "aiohttp>=3.11.12",
    ]

    for dep in test_deps:
        try:
            __import__(dep.split(">=")[0].replace("-", "_"))
        except ImportError:
            print(f"Installing {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True)

    # Run tests with different configurations
    tests_passed = True

    # 1. Run unit tests
    if not run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_models.py",
            "tests/test_services.py",
            "-v",
            "--tb=short",
        ],
        "Unit Tests",
    ):
        tests_passed = False

    # 2. Run database tests
    if not run_command(
        [sys.executable, "-m", "pytest", "tests/test_database.py", "-v", "--tb=short"],
        "Database Tests",
    ):
        tests_passed = False

    # 3. Run API tests
    if not run_command(
        [sys.executable, "-m", "pytest", "tests/test_api.py", "-v", "--tb=short"],
        "API Tests",
    ):
        tests_passed = False

    # 4. Run all tests with coverage
    if not run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-fail-under=70",
            "-v",
        ],
        "All Tests with Coverage",
    ):
        tests_passed = False

    # 5. Run linting
    if not run_command(
        [sys.executable, "-m", "ruff", "check", "app/", "tests/"], "Code Linting"
    ):
        tests_passed = False

    # 6. Run type checking
    if not run_command([sys.executable, "-m", "mypy", "app/"], "Type Checking"):
        tests_passed = False

    # Summary
    print(f"\n{'=' * 60}")
    if tests_passed:
        print("✅ All tests passed successfully!")
        print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("❌ Some tests failed!")
        sys.exit(1)
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
