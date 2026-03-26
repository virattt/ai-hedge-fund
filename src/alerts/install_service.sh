#!/bin/bash
# Install the options monitor as a macOS LaunchAgent
# It will run automatically on login and restart if it crashes

PROJECT_DIR="/Users/ianrahwan/Documents/Projects/ai-hedge-fund"
POETRY_BIN=$(which poetry)
PLIST_PATH="$HOME/Library/LaunchAgents/com.aihedgefund.optionsmonitor.plist"

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aihedgefund.optionsmonitor</string>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${POETRY_BIN}</string>
        <string>run</string>
        <string>python</string>
        <string>-m</string>
        <string>src.alerts.monitor</string>
        <string>--run</string>
        <string>--interval=60</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/monitor.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/monitor_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "Installed LaunchAgent at: $PLIST_PATH"
echo ""
echo "Commands:"
echo "  Start:   launchctl load $PLIST_PATH"
echo "  Stop:    launchctl unload $PLIST_PATH"
echo "  Status:  launchctl list | grep optionsmonitor"
echo "  Logs:    tail -f $PROJECT_DIR/monitor.log"
echo ""

# Load it now
launchctl load "$PLIST_PATH"
echo "Monitor started. It will:"
echo "  - Check positions every 60 seconds during market hours"
echo "  - Call your phone when alerts trigger"
echo "  - Restart automatically if it crashes"
echo "  - Start on login"
