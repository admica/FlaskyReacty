"""
User preferences endpoints and functionality
"""
from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from core import db, logger, rate_limit
import traceback
import json
import math

preferences_bp = Blueprint('preferences', __name__)

def generate_avatar_svg(seed: int, initial: str) -> str:
    """Generate a colorful geometric SVG avatar based on seed"""
    # Use seed to generate consistent colors and patterns
    rng = seed

    def get_next_random():
        nonlocal rng
        rng = (1103515245 * rng + 12345) & 0x7fffffff
        return rng
    
    def get_color():
        """Generate vibrant colors using HSL color space"""
        h = get_next_random() % 360  # Hue: 0-359
        s = 70 + (get_next_random() % 30)  # Saturation: 70-99%
        l = 45 + (get_next_random() % 20)  # Lightness: 45-64%
        return f"hsl({h}, {s}%, {l}%)"

    # Generate background gradient
    gradient_angle = get_next_random() % 360
    color1 = get_color()
    color2 = get_color()
    
    # Generate pattern elements
    pattern = []
    
    # Add some background shapes
    for i in range(4):  # Background shapes
        x = 10 + (get_next_random() % 80)
        y = 10 + (get_next_random() % 80)
        size = 30 + (get_next_random() % 40)
        opacity = 0.3 + (get_next_random() % 40) / 100
        
        shape_type = get_next_random() % 4
        color = get_color()
        
        if shape_type == 0:  # Circle
            pattern.append(f'<circle cx="{x}" cy="{y}" r="{size/2}" fill="{color}" opacity="{opacity}" />')
        elif shape_type == 1:  # Square
            pattern.append(f'<rect x="{x-size/2}" y="{y-size/2}" width="{size}" height="{size}" fill="{color}" opacity="{opacity}" transform="rotate({get_next_random() % 45} {x} {y})" />')
        elif shape_type == 2:  # Triangle
            points = f"{x},{y-size/2} {x-size/2},{y+size/2} {x+size/2},{y+size/2}"
            pattern.append(f'<polygon points="{points}" fill="{color}" opacity="{opacity}" />')
        else:  # Hexagon
            points = []
            for j in range(6):
                angle = j * 60
                px = x + size/2 * math.cos(math.radians(angle))
                py = y + size/2 * math.sin(math.radians(angle))
                points.append(f"{px},{py}")
            pattern.append(f'<polygon points="{" ".join(points)}" fill="{color}" opacity="{opacity}" />')

    # Add foreground elements
    for i in range(3):  # Foreground shapes
        x = 20 + (get_next_random() % 60)
        y = 20 + (get_next_random() % 60)
        size = 15 + (get_next_random() % 30)
        color = get_color()
        
        shape_type = get_next_random() % 3
        if shape_type == 0:  # Small circles
            pattern.append(f'<circle cx="{x}" cy="{y}" r="{size/3}" fill="{color}" />')
        elif shape_type == 1:  # Cross
            thickness = size / 8
            pattern.append(f'''
                <g transform="rotate({get_next_random() % 45} {x} {y})">
                    <rect x="{x-size/2}" y="{y-thickness/2}" width="{size}" height="{thickness}" fill="{color}" />
                    <rect x="{x-thickness/2}" y="{y-size/2}" width="{thickness}" height="{size}" fill="{color}" />
                </g>
            ''')
        else:  # Diamond
            points = f"{x},{y-size/2} {x+size/3},{y} {x},{y+size/2} {x-size/3},{y}"
            pattern.append(f'<polygon points="{points}" fill="{color}" />')

    # Create SVG with gradient background, pattern, and text overlay
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:{color1};stop-opacity:1" />
            <stop offset="100%" style="stop-color:{color2};stop-opacity:1" />
        </linearGradient>
        <filter id="shadow">
            <feDropShadow dx="0" dy="0" stdDeviation="2" flood-opacity="0.3"/>
        </filter>
    </defs>
    <rect width="100" height="100" fill="url(#grad)" />
    {"".join(pattern)}
    <text
        x="50"
        y="50"
        text-anchor="middle"
        dominant-baseline="central"
        font-family="Arial, sans-serif"
        font-size="40"
        font-weight="bold"
        fill="rgba(255,255,255,0.9)"
        filter="url(#shadow)"
    >{initial}</text>
</svg>'''
    
    return svg

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
        settings = json.dumps(data.get('settings', {}))  # Convert dict to JSON string

        # Validate theme
        if theme not in ['dark', 'light']:
            logger.warning(f"Invalid theme value: {theme}")
            return jsonify({"error": "Invalid theme value"}), 400

        # Update or insert preferences using the db function
        result = db("""
            INSERT INTO user_preferences (username, theme, avatar_seed, settings)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (username) 
            DO UPDATE SET 
                theme = EXCLUDED.theme,
                avatar_seed = EXCLUDED.avatar_seed,
                settings = EXCLUDED.settings
            RETURNING username, theme, avatar_seed
        """, (username, theme, avatar_seed, settings))

        if result:
            logger.info(f"Successfully updated preferences for user: {username}")
            return jsonify({"message": "Preferences updated successfully"}), 200
        else:
            logger.error(f"Failed to update preferences for user: {username}")
            return jsonify({"error": "Failed to update preferences"}), 500

    except Exception as e:
        logger.error(f"Error updating preferences for user {get_jwt_identity()}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to update preferences"}), 500

@preferences_bp.route('/api/v1/avatar/<int:seed>', methods=['GET'])
def get_avatar(seed):
    """Get avatar image based on seed value"""
    try:
        # Get username from request args or default to 'U'
        username = request.args.get('username', 'U')
        initial = username[0].upper()
        
        # Generate SVG avatar
        svg_content = generate_avatar_svg(seed, initial)
        
        # Return SVG with proper content type
        return Response(svg_content, mimetype='image/svg+xml')

    except Exception as e:
        logger.error(f"Error generating avatar: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to generate avatar"}), 500 