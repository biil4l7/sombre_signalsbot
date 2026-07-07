from app.utils.logger import logger

class UserManager:
    def __init__(self, db_manager):
        self.db = db_manager
        self.max_users = 6
        logger.info("User Manager initialized")
    
    def add_user(self, username, telegram_id=None, first_name=None, invite_code=None):
        success, message = self.db.add_user_with_invite(
            username=username,
            telegram_id=telegram_id,
            first_name=first_name,
            invite_code=invite_code
        )
        
        if success:
            logger.info(f"User auto-joined: {username}")
            return True, message
        else:
            logger.warning(f"Failed to auto-join: {username} - {message}")
            return False, message
    
    def generate_invite(self, bot_username, custom_code=None):
        invite_link, message = self.db.generate_invite_link(bot_username, custom_code)
        
        if invite_link:
            logger.info(f"Invite link generated: {invite_link}")
            return invite_link, message
        else:
            logger.warning(f"Failed to generate invite: {message}")
            return None, message
    
    def get_users(self):
        users = self.db.get_all_users()
        return users
    
    def get_user_count(self):
        count = self.db.get_user_count()
        return count
    
    def is_user_allowed(self, telegram_id):
        user = self.db.get_user_by_telegram_id(telegram_id)
        return user is not None and user['is_active']
