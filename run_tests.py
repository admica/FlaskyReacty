#!/opt/pcapserver/venv_linux/bin/python3
"""
PCAP Server Test Runner
Discovers and runs test suites from the tests directory.
"""
import os
import sys
import importlib
import pkgutil
from typing import List, Type
from rich.console import Console
from rich.table import Table

# Initialize rich console
console = Console()

class TestRunner:
    """Main test runner that discovers and executes test suites"""
    
    def __init__(self, base_url: str = "https://localhost:3000"):
        self.base_url = base_url
        self.results = []
    
    def discover_tests(self) -> List[Type]:
        """Discover all test classes in the tests directory"""
        test_classes = []
        tests_dir = os.path.join(os.path.dirname(__file__), 'tests')
        
        # Ensure tests directory exists
        if not os.path.exists(tests_dir):
            console.print("[red]Error: tests directory not found![/red]")
            sys.exit(1)
        
        # Add tests directory to Python path
        sys.path.insert(0, os.path.dirname(__file__))
        
        # Import all test modules
        for _, name, _ in pkgutil.iter_modules([tests_dir]):
            if name.startswith('test_'):
                try:
                    module = importlib.import_module(f'tests.{name}')
                    # Look for classes that end with 'Test'
                    for item_name in dir(module):
                        if item_name.endswith('Test'):
                            test_class = getattr(module, item_name)
                            if isinstance(test_class, type):  # Ensure it's a class
                                test_classes.append(test_class)
                except Exception as e:
                    console.print(f"[red]Error loading module {name}: {str(e)}[/red]")
        
        return test_classes
    
    def run(self) -> None:
        """Run all discovered tests"""
        test_classes = self.discover_tests()
        
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
                for method_name in dir(test_instance):
                    if method_name.startswith('test_'):
                        method = getattr(test_instance, method_name)
                        console.print(f"\nRunning: {method_name}")
                        try:
                            method()
                        except Exception as e:
                            console.print(f"[red]Test {method_name} failed: {str(e)}[/red]")
                
                # Run teardown if it exists
                if hasattr(test_instance, 'teardown'):
                    test_instance.teardown()
                
                # Store results
                if hasattr(test_instance, 'results'):
                    self.results.extend(test_instance.results)
            
            except Exception as e:
                console.print(f"[red]Error running {test_class.__name__}: {str(e)}[/red]")
    
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
                details = f"[red]{result.error}[/red]"
            elif result.response:
                try:
                    details = str(result.response)
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
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "https://localhost:3000"
    
    try:
        runner = TestRunner(base_url)
        runner.run()
        runner.print_summary()
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Tests interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Test execution failed: {str(e)}[/red]")
        sys.exit(1)

if __name__ == '__main__':
    main() 