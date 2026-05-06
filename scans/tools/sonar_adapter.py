import subprocess
import requests
from .base import ToolAdapter, ToolRunResult

class SonarAdapter(ToolAdapter):
    """Adapter for SonarQube scanner and API"""
    
    def __init__(self, sonar_host='http://localhost:9000', sonar_token=None, timeout=300):
        self.sonar_host = sonar_host
        self.sonar_token = sonar_token
        self.timeout = timeout
    
    def run(self, repo_path: str, config: dict = None) -> ToolRunResult:
        """
        Run SonarQube scan and fetch results
        
        Args:
            repo_path: Path to repository
            config: Dict with 'project_key' and optional 'sonar_token'
        
        Returns:
            ToolRunResult with issues JSON
        """
        if config is None:
            config = {}
        
        project_key = config.get('project_key')
        token = config.get('sonar_token', self.sonar_token)
        
        if not project_key:
            return ToolRunResult(
                success=False,
                raw_output='',
                error_message='project_key required in config',
                exit_code=-1
            )
        
        if not token:
            return ToolRunResult(
                success=False,
                raw_output='',
                error_message='sonar_token required',
                exit_code=-1
            )
        
        # Fetch issues from SonarQube API
        try:
            url = f"{self.sonar_host}/api/issues/search"
            params = {
                'componentKeys': project_key,
                'ps': 500,  # page size
                'resolved': 'false'
            }
            
            response = requests.get(
                url,
                params=params,
                auth=(token, ''),
                timeout=30
            )
            
            if response.status_code == 200:
                return ToolRunResult(
                    success=True,
                    raw_output=response.text,
                    exit_code=0
                )
            else:
                return ToolRunResult(
                    success=False,
                    raw_output=response.text,
                    error_message=f'SonarQube API error: {response.status_code}',
                    exit_code=response.status_code
                )
                
        except requests.exceptions.Timeout:
            return ToolRunResult(
                success=False,
                raw_output='',
                error_message='SonarQube API timeout',
                exit_code=-1
            )
        except requests.exceptions.ConnectionError:
            return ToolRunResult(
                success=False,
                raw_output='',
                error_message=f'Cannot connect to SonarQube at {self.sonar_host}',
                exit_code=-1
            )
        except Exception as e:
            return ToolRunResult(
                success=False,
                raw_output='',
                error_message=f'Error: {str(e)}',
                exit_code=-1
            )
