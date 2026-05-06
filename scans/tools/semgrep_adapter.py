import os
import shutil
import subprocess
import json

from django.conf import settings

from .base import ToolAdapter, ToolRunResult


class SemgrepAdapter(ToolAdapter):
    def __init__(self, timeout=300):
        self.timeout = timeout
        # Resolution order:
        #   1. SEMGREP_PATH setting / env var (explicit override)
        #   2. shutil.which('semgrep') (works when the active venv has semgrep on PATH)
        #   3. bare 'semgrep' (lets subprocess raise an informative error if missing)
        self.semgrep_path = (
            getattr(settings, 'SEMGREP_PATH', None)
            or os.getenv('SEMGREP_PATH')
            or shutil.which('semgrep')
            or 'semgrep'
        )
    
    def run(self, repo_path: str, config: dict = None) -> ToolRunResult:
        if config is None:
            config = {}
        
        ruleset = config.get('ruleset', 'auto')
        cmd = [
            self.semgrep_path,
            '--config', ruleset,
            '--json',
            '--quiet',
            repo_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode == 0 or result.returncode == 1:
                return ToolRunResult(
                    success=True,
                    raw_output=result.stdout,
                    exit_code=result.returncode
                )
            else:
                return ToolRunResult(
                    success=False,
                    raw_output=result.stdout,
                    error_message=result.stderr,
                    exit_code=result.returncode
                )
                
        except subprocess.TimeoutExpired:
            return ToolRunResult(
                success=False,
                raw_output='',
                error_message=f'Semgrep scan timed out after {self.timeout} seconds',
                exit_code=-1
            )
        except Exception as e:
            return ToolRunResult(
                success=False,
                raw_output='',
                error_message=f'Error: {str(e)}',
                exit_code=-1
            )
