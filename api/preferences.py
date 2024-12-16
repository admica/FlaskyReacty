"""
User preferences endpoints and functionality
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from core import db, logger, rate_limit
import traceback

preferences_bp = Blueprint('preferences', __name__)

@preferences_bp.route('/api/v1/preferences', methods=['GET'])
@jwt_required()
@rate_limit()
def get_preferences():
    """Get user preferences"""
    try:
        username = get_jwt_identity()
        logger.info(f"Getting preferences for user: {username}")
        
        # Get user preferences from database
        result = db("""
            SELECT theme, avatar_seed, settings
            FROM user_preferences
            WHERE username = %s
        """, (username,))

        if result and result[0]:
            prefs = {
                'theme': result[0][0],
                'avatar_seed': result[0][1],
                'settings': result[0][2]
            }
            logger.debug(f"Retrieved preferences for {username}: {prefs}")
            return jsonify(prefs), 200

        # If no preferences exist yet, return defaults
        logger.debug(f"No preferences found for {username}, returning defaults")
        return jsonify({
            'theme': 'dark',
            'avatar_seed': None,
            'settings': {}
        }), 200

    except Exception as e:
        logger.error(f"Error getting preferences for user {get_jwt_identity()}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to get preferences"}), 500

@preferences_bp.route('/api/v1/preferences', methods=['POST'])
@jwt_required()
@rate_limit()
def update_preferences():
    """Update user preferences"""
    try:
        username = get_jwt_identity()
        logger.info(f"Updating preferences for user: {username}")
        
        data = request.get_json()
        logger.debug(f"Received preference data: {data}")

        if not data:
            logger.warning("No preference data provided")
            return jsonify({"error": "No data provided"}), 400

        theme = data.get('theme', 'dark')
        avatar_seed = data.get('avatar_seed')
        settings = data.get('settings', {})

        # Validate theme
        if theme not in ['dark', 'light']:
            logger.warning(f"Invalid theme value: {theme}")
            return jsonify({"error": "Invalid theme value"}), 400

        # First check if user exists in preferences table
        check_result = db("SELECT 1 FROM user_preferences WHERE username = %s", (username,))
        if check_result:
            logger.debug(f"User {username} exists in preferences table")
        else:
            logger.debug(f"User {username} not found in preferences table, will create new entry")

        # Update or insert preferences
        logger.debug(f"Executing database operation for {username} - Theme: {theme}, Avatar Seed: {avatar_seed}")
        try:
            # Get a connection from the pool
            conn = db_pool.getconn()
            cur = conn.cursor()
            
            try:
                # Execute the update
                cur.execute("""
                    INSERT INTO user_preferences (username, theme, avatar_seed, settings)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (username) 
                    DO UPDATE SET 
                        theme = EXCLUDED.theme,
                        avatar_seed = EXCLUDED.avatar_seed,
                        settings = EXCLUDED.settings
                    RETURNING username, theme, avatar_seed
                """, (username, theme, avatar_seed, settings))
                
                # Verify the update
                cur.execute("SELECT theme, avatar_seed FROM user_preferences WHERE username = %s", (username,))
                verify_result = cur.fetchone()
                
                if verify_result:
                    saved_theme, saved_seed = verify_result
                    logger.info(f"Verified saved preferences for {username} - Theme: {saved_theme}, Seed: {saved_seed}")
                else:
                    logger.warning(f"Could not verify saved preferences for {username}")
                
                # Commit the transaction
                conn.commit()
                logger.debug("Transaction committed successfully")
                
            except Exception as db_error:
                conn.rollback()
                logger.error(f"Database operation failed, rolling back: {db_error}")
                logger.error(traceback.format_exc())
                raise
            finally:
                cur.close()
                db_pool.putconn(conn)
                
        except Exception as db_error:
            logger.error(f"Database operation failed: {db_error}")
            logger.error(traceback.format_exc())
            raise

        logger.info(f"Successfully updated preferences for user: {username}")
        return jsonify({"message": "Preferences updated successfully"}), 200

    except Exception as e:
        logger.error(f"Error updating preferences for user {get_jwt_identity()}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to update preferences"}), 500

@preferences_bp.route('/api/v1/avatar/<int:seed>', methods=['GET'])
def get_avatar(seed):
    """Get avatar image based on seed value"""
    try:
        # Here you would generate or retrieve an avatar image based on the seed
        # For now, we'll return a placeholder URL
        avatar_url = f"https://api.dicebear.com/7.x/bottts/svg?seed={seed}"
        return jsonify({"url": avatar_url}), 200

    except Exception as e:
        logger.error(f"Error getting avatar: {e}")
        return jsonify({"error": "Failed to get avatar"}), 500 