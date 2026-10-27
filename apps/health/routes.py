import datetime
import os
from flask import jsonify, current_app
from apps import db
from apps.health import blueprint
from icecream import ic

@blueprint.route('/health')
def health_check():
    """
    Health check endpoint that verifies:
    1. The application is running
    2. Database connection is working
    3. Environment variables are properly set
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "environment": os.getenv("FLASK_ENV", "unknown"),
        "checks": {}
    }
    
    # Check database connection
    try:
        # Simple query to verify DB connection
        result = db.session.execute("SELECT 1").scalar()
        health_status["checks"]["database"] = "connected" if result == 1 else "error"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = f"error: {str(e)}"
        ic(f"Health check database error: {str(e)}")
    
    # Check environment variables
    env_vars = [
        "DB_ENGINE", "DB_HOST", "DB_NAME", "DB_USERNAME", "DB_PORT"
    ]
    
    health_status["checks"]["environment_variables"] = {}
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Don't show actual values for security, just whether they exist
            health_status["checks"]["environment_variables"][var] = "set"
        else:
            health_status["checks"]["environment_variables"][var] = "missing"
            health_status["status"] = "unhealthy"
    
    # Return appropriate status code
    status_code = 200 if health_status["status"] == "healthy" else 500
    return jsonify(health_status), status_code
