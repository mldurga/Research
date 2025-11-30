"""
Authentication and Authorization Service
Handles Windows Authentication, AD integration, and PI Security
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from functools import lru_cache
from loguru import logger

from app.core.config import settings


class SecurityService:
    """Service for managing PI System security and authentication"""

    def __init__(self):
        """Initialize security service"""
        self.enable_windows_auth = settings.security.enable_windows_auth
        self.require_element_permissions = settings.security.require_element_permissions
        self.require_point_permissions = settings.security.require_point_permissions
        self.admin_groups = settings.security.admin_groups
        self.cache_permissions = settings.security.cache_permissions
        self.cache_ttl = settings.security.cache_ttl_seconds

        self._permission_cache = {}
        logger.info("Security service initialized")

    def get_user_identity(self, request_user: str) -> str:
        """
        Extract user identity from request

        Args:
            request_user: User from request (e.g., DOMAIN\\username)

        Returns:
            Normalized user identity
        """
        # Normalize user identity
        if "\\" in request_user:
            return request_user
        else:
            # Add domain if not present
            return f"DOMAIN\\{request_user}"

    def is_admin(self, user_identity: str) -> bool:
        """
        Check if user is an admin

        Args:
            user_identity: User identity

        Returns:
            True if user is admin
        """
        try:
            # Check if user belongs to admin groups
            # This is a simplified implementation
            # In production, integrate with Windows AD groups
            user_groups = self._get_user_groups(user_identity)

            for admin_group in self.admin_groups:
                if admin_group.lower() in [g.lower() for g in user_groups]:
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    def _get_user_groups(self, user_identity: str) -> List[str]:
        """
        Get AD groups for user

        Args:
            user_identity: User identity

        Returns:
            List of group names
        """
        # TODO: Implement actual AD group lookup using pywin32 or ldap
        # For now, return empty list
        # In Windows environment, you can use:
        # import win32net
        # import win32security
        return []

    @lru_cache(maxsize=1000)
    def check_element_permission(
        self,
        user_identity: str,
        element_path: str,
        permission: str = "read"
    ) -> bool:
        """
        Check if user has permission to access AF element

        Args:
            user_identity: User identity
            element_path: Path to AF element
            permission: Permission type (read, write, delete)

        Returns:
            True if user has permission
        """
        if not self.require_element_permissions:
            return True

        try:
            # Check cache first
            cache_key = f"{user_identity}:{element_path}:{permission}"

            if self.cache_permissions and cache_key in self._permission_cache:
                cached_result, cached_time = self._permission_cache[cache_key]
                if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                    return cached_result

            # TODO: Implement actual AF element security check using AF SDK
            # For now, return True (allow all)
            # In production, use AF SDK to check element security:
            # element = af_client.get_element_by_path(element_path)
            # security = element.Security
            # has_permission = security.CanRead(user_identity)

            result = True

            # Cache result
            if self.cache_permissions:
                self._permission_cache[cache_key] = (result, datetime.now())

            return result

        except Exception as e:
            logger.error(f"Error checking element permission: {e}")
            return False

    @lru_cache(maxsize=1000)
    def check_point_permission(
        self,
        user_identity: str,
        point_name: str,
        permission: str = "read"
    ) -> bool:
        """
        Check if user has permission to access PI Point

        Args:
            user_identity: User identity
            point_name: PI Point name
            permission: Permission type (read, write)

        Returns:
            True if user has permission
        """
        if not self.require_point_permissions:
            return True

        try:
            # Check cache first
            cache_key = f"{user_identity}:{point_name}:{permission}"

            if self.cache_permissions and cache_key in self._permission_cache:
                cached_result, cached_time = self._permission_cache[cache_key]
                if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                    return cached_result

            # TODO: Implement actual PI Point security check using AF SDK
            # For now, return True (allow all)
            # In production, use AF SDK to check point security:
            # point = pi_client.get_pi_point(point_name)
            # security = point.Security
            # has_permission = security.CanRead(user_identity)

            result = True

            # Cache result
            if self.cache_permissions:
                self._permission_cache[cache_key] = (result, datetime.now())

            return result

        except Exception as e:
            logger.error(f"Error checking point permission: {e}")
            return False

    def filter_elements_by_permission(
        self,
        user_identity: str,
        elements: List[Dict[str, Any]],
        permission: str = "read"
    ) -> List[Dict[str, Any]]:
        """
        Filter elements based on user permissions

        Args:
            user_identity: User identity
            elements: List of element dictionaries
            permission: Permission type

        Returns:
            Filtered list of elements
        """
        if not self.require_element_permissions:
            return elements

        filtered = []
        for element in elements:
            element_path = element.get("path", "")
            if self.check_element_permission(user_identity, element_path, permission):
                filtered.append(element)

        logger.debug(
            f"Filtered {len(elements)} elements to {len(filtered)} based on permissions"
        )
        return filtered

    def filter_points_by_permission(
        self,
        user_identity: str,
        points: List[str],
        permission: str = "read"
    ) -> List[str]:
        """
        Filter PI Points based on user permissions

        Args:
            user_identity: User identity
            points: List of point names
            permission: Permission type

        Returns:
            Filtered list of point names
        """
        if not self.require_point_permissions:
            return points

        filtered = []
        for point in points:
            if self.check_point_permission(user_identity, point, permission):
                filtered.append(point)

        logger.debug(
            f"Filtered {len(points)} points to {len(filtered)} based on permissions"
        )
        return filtered

    def clear_permission_cache(self):
        """Clear the permission cache"""
        self._permission_cache.clear()
        # Also clear lru_cache
        self.check_element_permission.cache_clear()
        self.check_point_permission.cache_clear()
        logger.info("Permission cache cleared")

    def validate_windows_auth(self, username: str, password: str) -> bool:
        """
        Validate Windows credentials

        Args:
            username: Username (DOMAIN\\user)
            password: Password

        Returns:
            True if credentials are valid
        """
        if not self.enable_windows_auth:
            return True

        try:
            # TODO: Implement Windows authentication validation
            # For Windows environment, use:
            # import win32security
            # token = win32security.LogonUser(
            #     username,
            #     domain,
            #     password,
            #     win32security.LOGON32_LOGON_NETWORK,
            #     win32security.LOGON32_PROVIDER_DEFAULT
            # )
            # return token is not None

            # For now, return True (development mode)
            return True

        except Exception as e:
            logger.error(f"Error validating Windows credentials: {e}")
            return False

    def create_access_token(
        self,
        user_identity: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token

        Args:
            user_identity: User identity
            expires_delta: Token expiration time

        Returns:
            JWT token string
        """
        try:
            from jose import jwt
            from datetime import datetime, timedelta

            if expires_delta is None:
                expires_delta = timedelta(hours=8)

            expire = datetime.utcnow() + expires_delta

            to_encode = {
                "sub": user_identity,
                "exp": expire,
                "type": "access"
            }

            # TODO: Use proper secret key from configuration
            secret_key = "your-secret-key-change-in-production"
            algorithm = "HS256"

            encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
            return encoded_jwt

        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise

    def verify_access_token(self, token: str) -> Optional[str]:
        """
        Verify JWT access token

        Args:
            token: JWT token string

        Returns:
            User identity if valid, None otherwise
        """
        try:
            from jose import jwt, JWTError

            # TODO: Use proper secret key from configuration
            secret_key = "your-secret-key-change-in-production"
            algorithm = "HS256"

            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            user_identity: str = payload.get("sub")

            if user_identity is None:
                return None

            return user_identity

        except JWTError as e:
            logger.error(f"Error verifying access token: {e}")
            return None
