#!/opt/pcapserver/venv_linux/bin/python3
"""
PCAP Server Test Runner
Discovers and runs test suites from the tests directory.

Usage:
    ./run_tests.py [base_url] [test_files...] [--max=N]

Examples:
    ./run_tests.py                         # Run all tests with default URL
    ./run_tests.py https://localhost:3000  # Run all tests with specific URL
    ./run_tests.py test_auth.py            # Run only auth tests with default URL
    ./run_tests.py test_auth test_sensors  # Run specific test files
    ./run_tests.py --max=1000              # Set maximum output length to 1000 chars
"""
import os
import sys
import importlib
import pkgutil
from typing import List, Type, Optional
from rich.console import Console
from rich.table import Table
from tests.base import BaseTest

# Initialize rich console
console = Console()

class TestRunner:
    """Main test runner that discovers and executes test suites"""

    def __init__(self, base_url: str = "https://localhost:3000", max_output_length: int = 150):
        self.base_url = base_url
        self.max_output_length = max_output_length
        self.results = []

    def discover_tests(self, specific_files: Optional[List[str]] = None) -> List[Type]:
        """
        Discover test classes in the tests directory.
        If specific_files is provided, only load those test files.
        """
        test_classes = []
        tests_dir = os.path.join(os.path.dirname(__file__), 'tests')

        # Ensure tests directory exists
        if not os.path.exists(tests_dir):
            console.print("[red]Error: tests directory not found![/red]")
            sys.exit(1)

        # Add tests directory to Python path
        sys.path.insert(0, os.path.dirname(__file__))

        if specific_files:
            # Load only specified test files
            for file_name in specific_files:
                # Strip .py extension if present
                module_name = file_name[:-3] if file_name.endswith('.py') else file_name
                try:
                    module = importlib.import_module(f'tests.{module_name}')
                    # Look for classes that end with 'Test'
                    for item_name in dir(module):
                        if item_name.endswith('Test'):
                            test_class = getattr(module, item_name)
                            # Only include classes that inherit from BaseTest but aren't BaseTest itself
                            if (isinstance(test_class, type) and
                                issubclass(test_class, BaseTest) and
                                test_class != BaseTest):
                                test_classes.append(test_class)
                except Exception as e:
                    console.print(f"[red]Error loading test file {file_name}: {str(e)}[/red]")
        else:
            # Load all test files
            for _, name, _ in pkgutil.iter_modules([tests_dir]):
                if name.startswith('test_'):
                    try:
                        module = importlib.import_module(f'tests.{name}')
                        for item_name in dir(module):
                            if item_name.endswith('Test'):
                                test_class = getattr(module, item_name)
                                # Only include classes that inherit from BaseTest but aren't BaseTest itself
                                if (isinstance(test_class, type) and 
                                    issubclass(test_class, BaseTest) and 
                                    test_class != BaseTest):
                                    test_classes.append(test_class)
                    except Exception as e:
                        console.print(f"[red]Error loading module {name}: {str(e)}[/red]")

        return test_classes

    def run(self, specific_files: Optional[List[str]] = None) -> None:
        """Run discovered tests"""
        test_classes = self.discover_tests(specific_files)

        if not test_classes:
            console.print("[yellow]No test classes found![/yellow]")
            return

        console.print(f"\n[bold]Found {len(test_classes)} test classes[/bold]")

        for test_class in test_classes:
            console.print(f"\n[bold blue]Running {test_class.__name__}[/bold blue]")

            try:
                # Initialize test class with base URL
                test_instance = test_class(self.base_url)

                # Run setup if it exists
                if hasattr(test_instance, 'setup'):
                    test_instance.setup()

                # Run all test methods
                for method_name in sorted(dir(test_instance)):
                    if method_name.startswith('test_'):
                        method = getattr(test_instance, method_name)
                        console.print(f"\nRunning: {method_name}")
                        try:
                            method()
                        except Exception as e:
                            # Add error to results instead of printing
                            test_instance.add_result(TestResult(
                                method_name,
                                False,
                                None,
                                str(e)
                            ))

                # Run teardown if it exists
                if hasattr(test_instance, 'teardown'):
                    test_instance.teardown()

                # Store results
                if hasattr(test_instance, 'results'):
                    self.results.extend(test_instance.results)

            except Exception as e:
                console.print(f"[red]Error running {test_class.__name__}: {str(e)}[/red]")

    def truncate_text(self, text: str) -> str:
        """Truncate text to max_output_length, adding ellipsis if needed"""
        if not text or len(text) <= self.max_output_length:
            return text
        return text[:self.max_output_length] + "..."

    def print_summary(self) -> None:
        """Print test execution summary"""
        if not self.results:
            console.print("\n[yellow]No test results to display[/yellow]")
            return

        console.print("\n[bold]Test Execution Summary:[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Test Name")
        table.add_column("Result")
        table.add_column("Details", overflow="fold")

        success_count = 0
        for result in self.results:
            status = "[green]Success[/green]" if result.success else "[red]Failed[/red]"
            if result.success:
                success_count += 1

            details = ""
            if result.error:
                details = f"[red]{self.truncate_text(str(result.error))}[/red]"
            elif result.response:
                try:
                    details = self.truncate_text(str(result.response))
                except:
                    details = "Unable to format response"

            table.add_row(
                result.name,
                status,
                details
            )

        console.print(table)
        total = len(self.results)
        success_rate = (success_count / total * 100) if total > 0 else 0
        console.print(f"\nSuccess Rate: {success_rate:.1f}% ({success_count}/{total})")

def main():
    """Main entry point"""
    args = sys.argv[1:]
    base_url = "https://localhost:3000"
    test_files = []
    max_output_length = 150 # Default number of lines

    # Parse arguments
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith('http'):
            base_url = arg
        elif arg.startswith('--max='):
            try:
                max_output_length = int(arg.split('=')[1])
            except (IndexError, ValueError):
                console.print("[red]Invalid --max value. Using default.[/red]")
        elif arg.endswith('.py') or arg.startswith('test_'):
            test_files.append(arg)
        i += 1

    try:
        runner = TestRunner(base_url, max_output_length)
        runner.run(test_files if test_files else None)
        runner.print_summary()

    except KeyboardInterrupt:
        console.print("\n[yellow]Tests interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Test execution failed: {str(e)}[/red]")
        sys.exit(1)

if __name__ == '__main__':
    main() 
