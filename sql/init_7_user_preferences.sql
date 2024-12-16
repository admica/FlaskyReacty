-- User preferences and settings table
-- This table stores user-specific settings, avatar preferences, and tracks user activity
-- The settings column uses JSONB for flexible extension of user preferences without schema changes

CREATE TABLE IF NOT EXISTS user_preferences (
    username VARCHAR(255) PRIMARY KEY,  -- Store preferences for any authenticated user
    avatar_seed INTEGER NOT NULL DEFAULT floor(random() * 1000000),  -- For consistent avatar generation
    theme VARCHAR(50) DEFAULT 'dark',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    login_count INTEGER DEFAULT 1,
    settings JSONB DEFAULT '{}'::jsonb,  -- Extensible settings storage
    CONSTRAINT valid_theme CHECK (theme IN ('dark', 'light'))
);

-- Create index on username for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_preferences_username ON user_preferences(username);

-- Function to update user login statistics
CREATE OR REPLACE FUNCTION update_user_login_stats()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_preferences (username, last_login, login_count)
    VALUES (NEW.username, CURRENT_TIMESTAMP, 1)
    ON CONFLICT (username) 
    DO UPDATE SET 
        last_login = CURRENT_TIMESTAMP,
        login_count = user_preferences.login_count + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for user login tracking (if it doesn't exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'user_login_trigger'
    ) THEN
        CREATE TRIGGER user_login_trigger
        AFTER INSERT ON user_sessions
        FOR EACH ROW
        EXECUTE FUNCTION update_user_login_stats();
    END IF;
END $$;

-- Grant appropriate permissions
GRANT SELECT, INSERT, UPDATE ON user_preferences TO pcapuser;
