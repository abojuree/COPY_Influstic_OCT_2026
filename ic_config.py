"""
Configure icecream library for different environments.
This module disables icecream in production to prevent recursion errors.
"""
import os
import sys

def configure_icecream():
    """
    Configure the icecream library based on the environment.
    In production, icecream is disabled to prevent recursion errors.
    """
    # Check if we're running on Render.com or in production
    is_production = os.environ.get('FLASK_ENV') != 'development' or 'render' in os.environ.get('RENDER', '').lower()
    
    if is_production:
        # Disable icecream in production by making ic a no-op function
        from icecream import ic, install
        ic.disable()
        
        # Create a no-op function to replace ic
        def no_op(*args, **kwargs):
            return args[0] if args else None
        
        # Replace ic with the no-op function
        sys.modules['icecream'].ic = no_op
        install()
        
        print("Icecream debugging disabled in production environment")
