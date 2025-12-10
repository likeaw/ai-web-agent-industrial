#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Web Agent - Main Launcher
Unified launcher with English-only UI to avoid encoding issues
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Tuple

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'
    
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class AgentLauncher:
    """AI Web Agent Launcher"""
    
    def __init__(self):
        # 脚本位于 scripts/，项目根目录为父级
        self.project_root = Path(__file__).parent.parent.absolute()
        self.python_exe = self.project_root / "python" / "python.exe"
        self.pip_exe = self.project_root / "python" / "Scripts" / "pip.exe"
        self.logs_dir = self.project_root / "logs"
        self.temp_dir = self.project_root / "temp"
        self.deps_flag = self.project_root / ".deps_installed"
        
        if RICH_AVAILABLE:
            try:
                self.console = Console(encoding='utf-8', force_terminal=True)
            except Exception:
                self.console = None
        else:
            self.console = None
    
    def print_header(self):
        """Print header"""
        if self.console:
            try:
                self.console.print(Panel.fit(
                    "[bold cyan]AI Web Agent - Industrial[/bold cyan]\n[dim]Intelligent Web Automation[/dim]",
                    border_style="cyan"
                ))
            except Exception:
                print("\n" + "=" * 50)
                print("  AI Web Agent - Industrial")
                print("  Intelligent Web Automation")
                print("=" * 50 + "\n")
        else:
            print("\n" + "=" * 50)
            print("  AI Web Agent - Industrial")
            print("  Intelligent Web Automation")
            print("=" * 50 + "\n")
    
    def check_python(self) -> bool:
        """Check Python installation"""
        if not self.python_exe.exists():
            msg = f"ERROR: Python not found!\nExpected: {self.python_exe}\nPlease run setup_python_env.cmd first"
            if self.console:
                try:
                    self.console.print("[red]X Python not found![/red]")
                    self.console.print(f"[yellow]Expected: {self.python_exe}[/yellow]")
                    self.console.print("[yellow]Please run setup_python_env.cmd first[/yellow]")
                except Exception:
                    print(msg)
            else:
                print(msg)
            return False
        
        if self.console:
            try:
                self.console.print("[green]V Python found[/green]")
            except Exception:
                print("Python found")
        return True
    
    def check_pip(self) -> bool:
        """Check pip installation"""
        if not self.pip_exe.exists():
            msg = "ERROR: pip not found!\nPlease run setup_python_env.cmd first"
            if self.console:
                try:
                    self.console.print("[red]X pip not found![/red]")
                    self.console.print("[yellow]Please run setup_python_env.cmd first[/yellow]")
                except Exception:
                    print(msg)
            else:
                print(msg)
            return False
        
        if self.console:
            try:
                self.console.print("[green]V pip found[/green]")
            except Exception:
                print("pip found")
        return True
    
    def check_dependencies(self) -> Tuple[bool, List[str]]:
        """Check required dependencies"""
        missing = []
        deps = ["pydantic", "playwright", "rich", "dotenv", "requests"]
        
        if self.console:
            try:
                with self.console.status("[bold yellow]Checking dependencies..."):
                    for dep in deps:
                        try:
                            result = subprocess.run(
                                [str(self.python_exe), "-c", f"import {dep}"],
                                capture_output=True,
                                timeout=5
                            )
                            if result.returncode != 0:
                                missing.append(dep)
                        except Exception:
                            missing.append(dep)
            except Exception:
                print("Checking dependencies...")
                for dep in deps:
                    try:
                        result = subprocess.run(
                            [str(self.python_exe), "-c", f"import {dep}"],
                            capture_output=True,
                            timeout=5
                        )
                        if result.returncode != 0:
                            missing.append(dep)
                    except Exception:
                        missing.append(dep)
        else:
            print("Checking dependencies...")
            for dep in deps:
                try:
                    result = subprocess.run(
                        [str(self.python_exe), "-c", f"import {dep}"],
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode != 0:
                        missing.append(dep)
                except Exception:
                    missing.append(dep)
        
        return len(missing) == 0, missing
    
    def install_dependencies(self) -> bool:
        """Install dependencies"""
        if self.console:
            try:
                self.console.print("[yellow]Installing dependencies...[/yellow]")
                self.console.print("[dim]This may take a few minutes...[/dim]")
            except Exception:
                print("Installing dependencies...")
                print("This may take a few minutes...")
        
        requirements_file = self.project_root / "requirements.txt"
        if not requirements_file.exists():
            msg = "ERROR: requirements.txt not found!"
            if self.console:
                try:
                    self.console.print(f"[red]X {msg}[/red]")
                except Exception:
                    print(msg)
            else:
                print(msg)
            return False
        
        try:
            result = subprocess.run(
                [str(self.pip_exe), "install", "-r", str(requirements_file)],
                cwd=str(self.project_root),
                timeout=600
            )
            
            if result.returncode == 0:
                self.deps_flag.touch()
                msg = "Dependencies installed successfully"
                if self.console:
                    try:
                        self.console.print(f"[green]V {msg}[/green]")
                    except Exception:
                        print(msg)
                else:
                    print(msg)
                return True
            else:
                msg = "Failed to install dependencies"
                if self.console:
                    try:
                        self.console.print(f"[red]X {msg}[/red]")
                    except Exception:
                        print(msg)
                else:
                    print(msg)
                return False
        except subprocess.TimeoutExpired:
            msg = "Installation timeout"
            if self.console:
                try:
                    self.console.print(f"[red]X {msg}[/red]")
                except Exception:
                    print(msg)
            else:
                print(msg)
            return False
        except Exception as e:
            msg = f"Installation error: {e}"
            if self.console:
                try:
                    self.console.print(f"[red]X {msg}[/red]")
                except Exception:
                    print(msg)
            else:
                print(msg)
            return False
    
    def show_menu(self) -> str:
        """Show main menu"""
        if self.console:
            try:
                menu_table = Table(show_header=False, box=None, padding=(0, 2))
                menu_table.add_row("[cyan][1][/cyan]", "Run CLI (Start AI Agent)")
                menu_table.add_row("[cyan][2][/cyan]", "Run API Server")
                menu_table.add_row("[cyan][3][/cyan]", "Run Frontend")
                menu_table.add_row("[cyan][4][/cyan]", "Run Full Stack (API + Frontend)")
                menu_table.add_row("[cyan][5][/cyan]", "Clean Logs")
                menu_table.add_row("[cyan][6][/cyan]", "Clean Temp Files")
                menu_table.add_row("[cyan][7][/cyan]", "Clean All")
                menu_table.add_row("[cyan][8][/cyan]", "Configure Pip Mirror")
                menu_table.add_row("[cyan][9][/cyan]", "Reinstall Dependencies")
                menu_table.add_row("[cyan][Q][/cyan]", "Quit")
                
                self.console.print("\n")
                self.console.print(Panel(menu_table, title="Menu", border_style="cyan"))
                self.console.print()
                
                choice = Prompt.ask(
                    "[cyan]Select option[/cyan]",
                    choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "q", "Q"],
                    default="1"
                )
                return choice.upper()
            except Exception:
                # Fallback to plain text
                print("\nMenu:")
                print("  [1] Run CLI (Start AI Agent)")
                print("  [2] Run API Server")
                print("  [3] Run Frontend")
                print("  [4] Run Full Stack (API + Frontend)")
                print("  [5] Clean Logs")
                print("  [6] Clean Temp Files")
                print("  [7] Clean All")
                print("  [8] Configure Pip Mirror")
                print("  [9] Reinstall Dependencies")
                print("  [Q] Quit")
                choice = input("\nSelect option: ").strip().upper()
                return choice if choice else "1"
        else:
            print("\nMenu:")
            print("  [1] Run CLI (Start AI Agent)")
            print("  [2] Run API Server")
            print("  [3] Run Frontend")
            print("  [4] Run Full Stack (API + Frontend)")
            print("  [5] Clean Logs")
            print("  [6] Clean Temp Files")
            print("  [7] Clean All")
            print("  [8] Configure Pip Mirror")
            print("  [9] Reinstall Dependencies")
            print("  [Q] Quit")
            choice = input("\nSelect option: ").strip().upper()
            return choice if choice else "1"
    
    def run_cli(self):
        """Run CLI"""
        if self.console:
            try:
                self.console.clear()
                self.console.print("[bold cyan]Starting AI Web Agent CLI...[/bold cyan]\n")
            except Exception:
                print("\nStarting AI Web Agent CLI...\n")
        else:
            print("\nStarting AI Web Agent CLI...\n")
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        try:
            subprocess.run(
                [str(self.python_exe), "-m", "backend.src.cli"],
                cwd=str(self.project_root),
                env=env
            )
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        except Exception as e:
            print(f"Error: {e}")
    
    def run_api_server(self):
        """Run API server"""
        if self.console:
            try:
                self.console.print("[bold cyan]Starting API Server...[/bold cyan]\n")
            except Exception:
                print("\nStarting API Server...\n")
        else:
            print("\nStarting API Server...\n")
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        try:
            subprocess.run(
                [str(self.python_exe), "-m", "uvicorn", "backend.src.api_server:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=str(self.project_root),
                env=env
            )
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        except Exception as e:
            print(f"Error: {e}")
    
    def run_frontend(self):
        """Run frontend"""
        frontend_dir = self.project_root / "frontend"
        if not frontend_dir.exists():
            print("ERROR: Frontend directory not found!")
            return
        
        if self.console:
            try:
                self.console.print("[bold cyan]Starting Frontend Dev Server...[/bold cyan]\n")
            except Exception:
                print("\nStarting Frontend Dev Server...\n")
        else:
            print("\nStarting Frontend Dev Server...\n")
        
        try:
            subprocess.run(["npm", "run", "dev"], cwd=str(frontend_dir))
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        except FileNotFoundError:
            print("ERROR: npm not found! Please install Node.js from https://nodejs.org/")
        except Exception as e:
            print(f"Error: {e}")
    
    def run_full_stack(self):
        """Run full stack"""
        if self.console:
            try:
                self.console.print("[bold cyan]Starting Full Stack (API + Frontend)...[/bold cyan]\n")
            except Exception:
                print("\nStarting Full Stack (API + Frontend)...\n")
        else:
            print("\nStarting Full Stack (API + Frontend)...\n")
        
        # Start API server in background
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        try:
            api_process = subprocess.Popen(
                [str(self.python_exe), "-m", "uvicorn", "backend.src.api_server:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=str(self.project_root),
                env=env
            )
            
            # Start frontend
            frontend_dir = self.project_root / "frontend"
            if frontend_dir.exists():
                frontend_process = subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=str(frontend_dir)
                )
                
                print("API Server: http://localhost:8000")
                print("Frontend: http://localhost:3000")
                print("\nPress Ctrl+C to stop all servers...")
                
                try:
                    frontend_process.wait()
                except KeyboardInterrupt:
                    print("\nStopping servers...")
                    api_process.terminate()
                    frontend_process.terminate()
            else:
                print("ERROR: Frontend directory not found!")
                api_process.terminate()
        except Exception as e:
            print(f"Error: {e}")
    
    def clean_logs(self):
        """Clean logs"""
        if self.logs_dir.exists():
            import shutil
            shutil.rmtree(self.logs_dir)
            self.logs_dir.mkdir(exist_ok=True)
            msg = "Logs cleaned"
            if self.console:
                try:
                    self.console.print(f"[green]V {msg}[/green]")
                except Exception:
                    print(msg)
            else:
                print(msg)
        else:
            msg = "No logs directory found"
            if self.console:
                try:
                    self.console.print(f"[yellow]{msg}[/yellow]")
                except Exception:
                    print(msg)
            else:
                print(msg)
    
    def clean_temp(self):
        """Clean temp files"""
        if self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)
            self.temp_dir.mkdir(exist_ok=True)
            (self.temp_dir / "notes").mkdir(exist_ok=True)
            (self.temp_dir / "screenshots").mkdir(exist_ok=True)
            (self.temp_dir / "downloads").mkdir(exist_ok=True)
            msg = "Temp files cleaned"
            if self.console:
                try:
                    self.console.print(f"[green]V {msg}[/green]")
                except Exception:
                    print(msg)
            else:
                print(msg)
        else:
            msg = "No temp directory found"
            if self.console:
                try:
                    self.console.print(f"[yellow]{msg}[/yellow]")
                except Exception:
                    print(msg)
            else:
                print(msg)
    
    def configure_pip_mirror(self):
        """Configure pip mirror"""
        mirrors = {
            "1": ("Aliyun", "https://mirrors.aliyun.com/pypi/simple/"),
            "2": ("Tsinghua", "https://pypi.tuna.tsinghua.edu.cn/simple/"),
            "3": ("USTC", "https://pypi.mirrors.ustc.edu.cn/simple/"),
            "4": ("Douban", "https://pypi.douban.com/simple/"),
            "5": ("Official", "https://pypi.org/simple/"),
        }
        
        if self.console:
            try:
                mirror_table = Table(show_header=False, box=None, padding=(0, 2))
                for key, (name, _) in mirrors.items():
                    mirror_table.add_row(f"[cyan][{key}][/cyan]", name)
                mirror_table.add_row("[cyan][0][/cyan]", "Back")
                
                self.console.print("\n")
                self.console.print(Panel(mirror_table, title="Pip Mirror Source", border_style="cyan"))
                self.console.print()
                
                choice = Prompt.ask(
                    "[cyan]Select mirror[/cyan]",
                    choices=["0", "1", "2", "3", "4", "5"],
                    default="0"
                )
            except Exception:
                print("\nPip Mirror Source:")
                for key, (name, _) in mirrors.items():
                    print(f"  [{key}] {name}")
                print("  [0] Back")
                choice = input("\nSelect mirror: ").strip()
        else:
            print("\nPip Mirror Source:")
            for key, (name, _) in mirrors.items():
                print(f"  [{key}] {name}")
            print("  [0] Back")
            choice = input("\nSelect mirror: ").strip()
        
        if choice != "0" and choice in mirrors:
            name, url = mirrors[choice]
            try:
                subprocess.run(
                    [str(self.pip_exe), "config", "set", "global.index-url", url],
                    capture_output=True,
                    timeout=10
                )
                msg = f"Pip mirror configured: {name}"
                if self.console:
                    try:
                        self.console.print(f"[green]V {msg}[/green]")
                    except Exception:
                        print(msg)
                else:
                    print(msg)
            except Exception as e:
                msg = f"Failed to configure mirror: {e}"
                if self.console:
                    try:
                        self.console.print(f"[red]X {msg}[/red]")
                    except Exception:
                        print(msg)
                else:
                    print(msg)
    
    def reinstall_dependencies(self):
        """Reinstall dependencies"""
        if self.deps_flag.exists():
            self.deps_flag.unlink()
        
        if self.install_dependencies():
            msg = "Dependencies reinstalled successfully"
            if self.console:
                try:
                    self.console.print(f"[green]V {msg}[/green]")
                except Exception:
                    print(msg)
            else:
                print(msg)
        else:
            msg = "Failed to reinstall dependencies"
            if self.console:
                try:
                    self.console.print(f"[red]X {msg}[/red]")
                except Exception:
                    print(msg)
            else:
                print(msg)
    
    def run(self):
        """Main run loop"""
        self.print_header()
        
        if not self.check_python():
            input("\nPress Enter to exit...")
            return
        
        if not self.check_pip():
            input("\nPress Enter to exit...")
            return
        
        if not self.deps_flag.exists():
            all_installed, missing = self.check_dependencies()
            if not all_installed:
                msg = f"Missing dependencies: {', '.join(missing)}"
                if self.console:
                    try:
                        self.console.print(f"[yellow]{msg}[/yellow]")
                        if Confirm.ask("[cyan]Install missing dependencies now?[/cyan]", default=True):
                            if not self.install_dependencies():
                                input("\nPress Enter to exit...")
                                return
                    except Exception:
                        print(msg)
                        if input("Install missing dependencies now? (Y/n): ").strip().upper() != "N":
                            if not self.install_dependencies():
                                input("\nPress Enter to exit...")
                                return
                else:
                    print(msg)
                    if input("Install missing dependencies now? (Y/n): ").strip().upper() != "N":
                        if not self.install_dependencies():
                            input("\nPress Enter to exit...")
                            return
        
        while True:
            try:
                choice = self.show_menu()
                
                if choice == "1":
                    self.run_cli()
                elif choice == "2":
                    self.run_api_server()
                elif choice == "3":
                    self.run_frontend()
                elif choice == "4":
                    self.run_full_stack()
                elif choice == "5":
                    self.clean_logs()
                elif choice == "6":
                    self.clean_temp()
                elif choice == "7":
                    self.clean_logs()
                    self.clean_temp()
                elif choice == "8":
                    self.configure_pip_mirror()
                elif choice == "9":
                    self.reinstall_dependencies()
                elif choice == "Q":
                    if self.console:
                        try:
                            self.console.print("[cyan]Thank you for using AI Web Agent![/cyan]")
                        except Exception:
                            print("Thank you for using AI Web Agent!")
                    else:
                        print("Thank you for using AI Web Agent!")
                    break
                
                if choice != "1" and choice != "2" and choice != "3" and choice != "4":
                    input("\nPress Enter to continue...")
                    if self.console:
                        try:
                            self.console.clear()
                            self.print_header()
                        except Exception:
                            pass
                
            except KeyboardInterrupt:
                print("\nInterrupted by user")
                break
            except Exception as e:
                msg = f"Error: {e}"
                if self.console:
                    try:
                        self.console.print(f"[red]{msg}[/red]")
                    except Exception:
                        print(msg)
                else:
                    print(msg)
                import traceback
                traceback.print_exc()
                input("\nPress Enter to continue...")


def main():
    """Main entry point"""
    launcher = AgentLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
