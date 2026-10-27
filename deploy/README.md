# Linux Deployment Configuration
# ================================
# This directory contains systemd service and crontab configuration
# for deploying the Influencers Analytics Platform on a Linux server
# instead of Render.com.
#
# Setup Instructions:
# 1. Copy socialscannerw.service to /etc/systemd/system/
# 2. Enable and start: sudo systemctl enable --now socialscannerw.service
# 3. Install crontab: crontab deploy/crontab
# 4. Verify: sudo systemctl status socialscannerw
