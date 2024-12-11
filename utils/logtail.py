#!/opt/pcapserver/venv_linux/bin/python3
"""
Enhanced colorized log viewer for pcapserver logs with directory monitoring.
Usage: ./logtail.py [-f] [-n LINES] [--no-color] directory1 [directory2 ...] [file1 file2 ...]

Features:
- Monitors directories for new log files
- Colorized output based on log levels
- Supports following multiple files
- Can handle both direct file paths and directories
"""
import os
import sys
import time
import glob
import argparse
import re

# ANSI colors
COLORS = {
    'RESET': '\033[0m',
    'GRAY': '\033[90m',        # Debug
    'GREEN': '\033[32m',       # Info
    'YELLOW': '\033[33m',      # Warning
    'RED': '\033[31m',         # Error
    'RED_BOLD': '\033[1;31m',  # Critical/Exception
    'BLUE': '\033[34m',        # Logger name
    'MAGENTA': '\033[35m',      # Filename
    'ORANGE': '\033[38;5;208m'  # Orange
}

# Log level colors
LEVEL_COLORS = {
    'DEBUG': COLORS['GRAY'],
    'INFO': COLORS['GREEN'],
    'WARNING': COLORS['YELLOW'],
    'ERROR': COLORS['RED'],
    'CRITICAL': COLORS['RED_BOLD'],
    'EXCEPTION': COLORS['RED_BOLD']
}

def colorize(text, color):
    """Add color to text."""
    return f"{color}{text}{COLORS['RESET']}"

def format_line(line, filename=''):
    """Format a log line with colors."""
    # Match log format: 2024-10-31_10:11:12 myLogName INFO [myapp.py:42 myfunction] message
    match = re.match(
        r'(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\w+)\s+\[([^\]]+)\]\s+(.*)',
        line
    )
    if not match:
        return line

    timestamp, name, level, source, message = match.groups()
    color = LEVEL_COLORS.get(level, '')
    
    # Format with colors
    result = (
        f"{COLORS['GRAY']}{timestamp}{COLORS['RESET']} "
        f"{COLORS['BLUE']}{name}{COLORS['RESET']} "
        f"{color}{level}{COLORS['RESET']} "
        f"[{source}] "
        f"{color}{message}{COLORS['RESET']}"
    )

    # Add filename prefix if watching multiple files
    if filename:
        result = f"{COLORS['MAGENTA']}{os.path.basename(filename)}{COLORS['RESET']} {result}"

    return result

def scan_directory(path):
    """
    Scan directory for log files.
    Returns a set of full file paths.
    """
    if os.path.isdir(path):
        # Look for common log file extensions
        log_files = set()
        for ext in ['*.log', '*.log.[0-9]*', '*.out', '*.err']:
            log_files.update(glob.glob(os.path.join(path, ext)))
        return log_files
    return {path} if os.path.isfile(path) else set()

def tail_files(paths, follow=False, num_lines=10):
    """
    Tail and colorize log files, monitoring directories for new files.
    
    Args:
        paths: List of file paths or directory paths to monitor
        follow: Boolean indicating whether to follow the files (like tail -f)
        num_lines: Number of lines to show initially from each file
    """
    known_files = set()
    file_handles = {}
    
    # Separate directories and direct file paths
    directories = {p for p in paths if os.path.isdir(p)}
    direct_files = {p for p in paths if os.path.isfile(p)}
    
    def scan_all_paths():
        """Scan all directories and combine with direct file paths."""
        all_files = set()
        for directory in directories:
            all_files.update(scan_directory(directory))
        all_files.update(direct_files)
        return all_files
    
    # Initial file scan and reading
    current_files = scan_all_paths()
    for filepath in current_files:
        try:
            with open(filepath) as f:
                lines = f.readlines()
                start = max(0, len(lines) - num_lines)
                for line in lines[start:]:
                    print(format_line(line.strip(), filepath if len(current_files) > 1 else ''))
                
                if follow:
                    f = open(filepath)
                    f.seek(0, 2)  # Seek to end
                    file_handles[filepath] = f
                    known_files.add(filepath)
                    
        except Exception as e:
            print(f"Error opening {filepath}: {e}", file=sys.stderr)

    # Follow mode
    if not follow:
        return

    try:
        last_scan_time = time.time()
        scan_interval = 1.0  # Scan for new files every second
        
        while True:
            current_time = time.time()
            
            # Periodically scan for new files
            if current_time - last_scan_time >= scan_interval:
                current_files = scan_all_paths()
                new_files = current_files - known_files
                
                # Handle new files
                for filepath in new_files:
                    try:
                        f = open(filepath)
                        f.seek(0, 2)  # Seek to end
                        file_handles[filepath] = f
                        known_files.add(filepath)
                        print(colorize(f"\nNow watching {filepath}", COLORS['ORANGE']))
                    except Exception as e:
                        print(f"Error opening new file {filepath}: {e}", file=sys.stderr)
                
                last_scan_time = current_time
            
            # Read from all files
            updated = False
            for filepath, f in list(file_handles.items()):
                try:
                    line = f.readline()
                    if line:
                        print(format_line(line.strip(), filepath if len(known_files) > 1 else ''))
                        updated = True
                except Exception as e:
                    print(f"Error reading {filepath}: {e}", file=sys.stderr)
                    # Try to reopen on error
                    try:
                        new_f = open(filepath)
                        new_f.seek(0, 2)
                        file_handles[filepath] = new_f
                        f.close()
                    except Exception:
                        del file_handles[filepath]
                        known_files.remove(filepath)
            
            if not updated:
                time.sleep(0.1)  # Prevent tight loop

    except KeyboardInterrupt:
        print("\nStopping log tail...")
    finally:
        for f in file_handles.values():
            try:
                f.close()
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(
        description='Enhanced colorized log viewer with directory monitoring',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s -f /var/log/myapp/        # Monitor all logs in directory
    %(prog)s -f -n 50 *.log            # Show last 50 lines of each log
    %(prog)s /var/log/myapp/ file.log  # Monitor both directory and specific file
        """
    )
    parser.add_argument('paths', nargs='+', help='Directories or files to watch (supports wildcards)')
    parser.add_argument('-f', '--follow', action='store_true', help='Follow the files (like tail -f)')
    parser.add_argument('-n', '--lines', type=int, default=10, help='Number of lines to show (default: 10)')
    args = parser.parse_args()

    # Expand any glob patterns in the paths
    expanded_paths = set()
    for path in args.paths:
        expanded = glob.glob(path)
        if expanded:
            expanded_paths.update(expanded)
        else:
            print(f"Warning: No matches found for {path}", file=sys.stderr)

    if not expanded_paths:
        print("Error: No valid paths specified", file=sys.stderr)
        sys.exit(1)

    tail_files(expanded_paths, args.follow, args.lines)

if __name__ == '__main__':
    main()