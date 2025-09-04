# Valorant-True-Stretch-2.4
A tool that automatically applies a true stretch resolution for Valorant on Windows. By default, Valorant only stretches the UI, not the actual game world. This helper edits the configuration files so the game truly runs stretched.

## What is True Stretch?
True stretch allows you to play VALORANT at a lower resolution (like 1280x1024) while stretching it to fill your monitor. This makes player models appear wider and can provide a competitive advantage, similar to stretched resolutions in CS:GO.

## Features
- **Auto-Detection** - Automatically finds VALORANT config files and detects your native resolution
- **Quick Presets** - Pre-configured resolution combinations for common setups
- **Safe Backups** - Creates backups of original config files with diff previews
- **Preview Mode** - See exactly what changes will be made before applying
- **Desktop Resolution** - Optionally change Windows desktop resolution automatically
- **User-Friendly** - Manages both root and user-specific config files
- **Verification** - Ensures VALORANT is properly configured before making changes

## Supported Resolutions
You can add custom resolution or select one.

### Native Resolutions
- 3840x2160 (4K)
- 2560x1440 (1440p)
- 1920x1080 (1080p)
- 2560x1080 (Ultrawide)
- 3440x1440 (Ultrawide)

### Target Stretch Resolutions
- 1920x1080, 1680x1050, 1440x1080
- 1280x1024, 1100x1080, 1080x1080
- 1280x960, 1024x768

## Requirements

- **Windows 10/11** (uses Windows display APIs)
- **Python 3.6 or higher**
- **VALORANT** installed and launched at least once
- **Required Python packages:** `ttkbootstrap`, `pillow`

## Installation

### Method 1: Automatic (Recommended)
1. Download or clone this repository
2. Run `install_requirements.bat` as Administrator
3. Run `ValorantTrueStretch_GUI_2.0.py`

### Method 2: Manual
```bash
# Install Python dependencies
pip install ttkbootstrap pillow

# Run the application
python ValorantTrueStretch_GUI_2.0.py
```

## Usage Guide

### Initial Setup (Important!)
1. **Launch VALORANT** and set it to:
   - **Fullscreen mode** (not windowed/borderless)
   - **Your native resolution** (e.g., 2560x1440)
   - **Display Mode: Fill** (not letterbox)
2. **Close VALORANT completely** (Riot Client can stay open)

### Using the Tool
1. **Launch the application**
2. **Choose your resolutions:**
   - **Native:** Your monitor's native resolution
   - **Target:** The stretched resolution you want to use
3. **Click "VERIFY (F1)"** to check your setup
4. **Click "PREVIEW (F2)"** to see what changes will be made
5. **Click "APPLY (Ctrl+Enter)"** to apply the configuration
6. **Optional:** Enable "Also change Windows desktop to target" for automatic desktop resolution switching
7. **Launch VALORANT** - it should now run in stretched resolution

### Keyboard Shortcuts
- `F1` - Verify configuration
- `F2` - Preview changes
- `Ctrl+Enter` - Apply changes
- `Ctrl+L` - Clear log

## Advanced Features

### Quick Buttons
Create custom preset buttons for your favorite resolution combinations:
- Click "Add Quick Button" to create new presets
- Use "Manage..." to reorder or remove presets

### Backup System
- Automatically creates timestamped backups in `Documents/ValorantTrueStretch_Backups`
- Includes diff files showing exactly what was changed
- Can be disabled if you prefer not to create backups

### Configuration Paths
- Auto-detects VALORANT config directory
- Manages both global and user-specific settings files
- Handles multiple user profiles automatically

## ⚠Important Notes

- **Always close VALORANT completely** before using this tool
- **The Riot Client can remain open** - only VALORANT needs to be closed
- **Initial setup is crucial** - VALORANT must be run once in native fullscreen mode
- **Desktop resolution** should match your target resolution when playing
- **Backups are recommended** in case you need to revert changes

## Troubleshooting

### "Native check failed" Error
This means VALORANT hasn't been properly configured for your native resolution:
1. Launch VALORANT
2. Set to Fullscreen mode at your native resolution
3. Set Display Mode to "Fill" (not letterbox)
4. Close VALORANT and try again
5. If issues persist, check "Force apply" to bypass the check

### Config Files Not Found
1. Make sure VALORANT has been launched at least once
2. Check that the config path is correct in the "Paths & Backups" section
3. Try clicking "Detect" to auto-find the config directory

### Resolution Not Applying
1. Ensure Windows desktop resolution matches your target resolution
2. Launch VALORANT after applying changes
3. Check that VALORANT is still in Fullscreen mode

## Reverting Changes

To revert to normal resolution:
1. Set both Native and Target to your monitor's native resolution
2. Apply the configuration
3. Change Windows desktop back to native resolution
4. Launch VALORANT

Or restore from backups in the backup directory.

---

**Credit:** Made by GlitchFL - credit required if you share or modify this tool.

## Disclaimer

- This tool modifies VALORANT configuration files but does **not** inject into the game process
- Use at your own risk - while generally safe, any modification of game files carries inherent risk
- This tool is not affiliated with Riot Games
- Always keep backups of your original configuration files

## Version History

- **v2.4** - Current version with modern GUI and enhanced features
- Features auto-detection, backup system, and desktop resolution management

---

**Enjoy your stretched VALORANT experience!**
