"""
User preferences tests for PCAP Server.
Tests getting and updating user preferences.
"""
from .base import BaseTest, TestResult

class PreferencesTest(BaseTest):
    """Test suite for user preferences endpoints"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.access_token = None
        self.current_preferences = None
    
    def setup(self) -> None:
        """Setup required for preferences tests - login first"""
        result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": self.auth_username,
                "password": self.auth_password
            },
            auth=False
        )
        
        if result['success']:
            self.access_token = result['response']['access_token']
        else:
            raise Exception("Failed to login for preferences tests")
    
    def test_get_preferences(self) -> None:
        """Test getting current preferences"""
        result = self.request(
            "GET",
            "/api/v1/preferences",
            auth=True,
            auth_token=self.access_token
        )
        
        # Store current preferences for later tests
        if result['success']:
            self.current_preferences = result['response']
        
        self.add_result(TestResult(
            "Get Current Preferences",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
    def test_update_theme(self) -> None:
        """Test updating theme preference"""
        if not self.current_preferences:
            self.add_result(TestResult(
                "Update Theme",
                False,
                None,
                "Cannot test theme update: No current preferences available"
            ))
            return
        
        # Toggle theme
        current_theme = self.current_preferences.get('theme', 'dark')
        new_theme = 'light' if current_theme == 'dark' else 'dark'
        
        # Update theme
        update_result = self.request(
            "POST",
            "/api/v1/preferences",
            data={
                'theme': new_theme,
                'avatar_seed': self.current_preferences.get('avatar_seed')
            },
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            f"Update Theme to {new_theme}",
            update_result['success'],
            update_result['response'],
            update_result.get('error')
        ))
        
        # Verify theme change
        verify_result = self.request(
            "GET",
            "/api/v1/preferences",
            auth=True,
            auth_token=self.access_token
        )
        
        theme_verified = (verify_result['success'] and 
                         verify_result['response'].get('theme') == new_theme)
        
        self.add_result(TestResult(
            "Verify Theme Change",
            theme_verified,
            verify_result['response'],
            None if theme_verified else "Theme not updated correctly"
        ))
        
        # Revert theme
        revert_result = self.request(
            "POST",
            "/api/v1/preferences",
            data={
                'theme': current_theme,
                'avatar_seed': self.current_preferences.get('avatar_seed')
            },
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            f"Revert Theme to {current_theme}",
            revert_result['success'],
            revert_result['response'],
            revert_result.get('error')
        ))
    
    def teardown(self) -> None:
        """Cleanup after preferences tests - logout"""
        if self.access_token:
            self.request(
                "POST",
                "/api/v1/logout",
                data={},
                auth=True,
                auth_token=self.access_token
            ) 