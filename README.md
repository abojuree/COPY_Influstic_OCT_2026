# Social Scanner Web

A web application for scanning and monitoring social media profiles across multiple platforms.

## Overview

Social Scanner Web is designed to track and analyze social media profiles. It provides automated scanning capabilities through scheduled cron jobs and offers a comprehensive admin interface for monitoring scan results and platform performance.

## Features

- **Multi-platform Scanning**: Supports scanning profiles across various social media platforms
- **Scheduled Scanning**: Automated scanning via Render.com's cron service
- **Admin Dashboard**: Monitor scan performance and platform-specific metrics
- **Email Notifications**: Receive alerts for scan failures or high failure rates
- **Database Backup**: Export and backup functionality for data preservation

## Technology Stack

- **Backend**: Flask (Python 3.11+)
- **Database**: PostgreSQL
- **Deployment**: Render.com
- **Scheduling**: Render.com cron jobs
- **Frontend**: HTML, CSS, JavaScript, Bootstrap

## Project Structure

| Directory | Description |
|-----------|-------------|
| authentication | Users' management, authorization and authentication codes |
| content_types | Content management codes |
| globals | Global code, contains general functions used by all other routes |
| home | Home page and search function |
| profiles | Influencers main profiles management |
| reports | Reports codes |
| social | Social account management |
| static | Contains static resources, images, css, js, svg, logos, icons, fonts |
| templates | HTML files |

## Deployment

This application is configured for deployment on Render.com using the following components:

1. **Web Service**: Hosts the main application
2. **Cron Job**: Runs scheduled scans every 2 days at 6:00 AM
3. **PostgreSQL Database**: Stores all application data

## Development Setup

1. Clone the repository:
   ```
   git clone https://github.com/engziada/SocialScannerWeb.git
   cd SocialScannerWeb
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables (copy .env.dev to .env for local development)

4. Run the application:
   ```
   python run.py
   ```

## Database Migrations

If you need to fix migration issues:

1. To merge multiple migration heads:
   ```
   python fix_migrations.py
   ```

2. For a complete migration reset (development only):
   ```
   python reset_migrations.py
   ```

## Maintenance

- **Database Cleanup**: The application automatically keeps only the last 3 scan logs
- **Monitoring**: Check the admin dashboard for platform performance metrics
- **Notifications**: Configure email settings to receive alerts for scan issues

## License

All rights reserved. This codebase is proprietary and confidential.

Last updated: 2025-05-20

## Project Statistics

Date: 2024-05-09
Total: 1918 files, 55040 codes, 2197 comments, 6318 blanks, all 63555 lines

### Languages
| Language | Files | Code | Comment |
|----------|-------|------|---------|
| XML | 1,584 | 17,892 | 33 |
| CSS | 23 | 17,266 | 256 |
| JavaScript | 179 | 6,519 | 896 |
| YAML | 1 | 4,505 | 0 |
| SCSS | 59 | 4,040 | 373 |
| HTML | 32 | 2,673 | 360 |
| Python | 37 | 2,041 | 279 |
| JSON | 3 | 104 | 0 |
