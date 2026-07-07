from app.utils.logger import logger

class UserManager:
    """User management for the signal bot with auto-join via invite links"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.max_users = 6
        logger.info("User Manager initialized with Auto-Join system")
    
    def add_user(self, username, telegram_id=None, first_name=None, invite_code=None):
        """Add a user via invite code"""
        success, message = self.db.add_user_with_invite(
            username=username,
            telegram_id=telegram_id,
            first_name=first_name,
            invite_code=invite_code
        )
        
        if success:
            logger.info(f"User auto-joined: {username} (ID: {telegram_id})")
            return True, message
        else:
            logger.warning(f"Failed to auto-join user: {username} - {message}")
            return False, message
    
    def generate_invite(self, bot_username, custom_code=None):
        """Generate an invite link"""
        invite_link, message = self.db.generate_invite_link(bot_username, custom_code)
        
        if invite_link:
            logger.info(f"Invite link generated: {invite_link}")
            return invite_link, message
        else:
            logger.warning(f"Failed to generate invite: {message}")
            return None, message
    
    def get_users(self):
        """Get all active users"""
        users = self.db.get_all_users()
        logger.info(f"Retrieved {len(users)} active users")
        return users
    
    def get_user_count(self):
        """Get number of active users"""
        count = self.db.get_user_count()
        logger.info(f"Active user count: {count}/{self.max_users}")
        return count
    
    def is_user_allowed(self, telegram_id):
        """Check if a user is allowed"""
        user = self.db.get_user_by_telegram_id(telegram_id)
        allowed = user is not None and user['is_active']
        
        if not allowed:
            logger.warning(f"User {telegram_id} is not in the allowed list")
        else:
            logger.debug(f"User {telegram_id} is authorized")
        
        return allowed
    
    def get_user_stats(self, telegram_id):
        """Get user statistics"""
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user:
            return None
        
        return {
            'username': user['username'],
            'first_name': user['first_name'],
            'joined_at': user['joined_at'],
            'is_active': user['is_active']
        }