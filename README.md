# A Debug Adapter for Debugging Python 2 within Foundry's Nuke

This adapter serves as a "middleman" between the Sublime Debugger plugin 
and a DAP implementation for python (ptvsd) injected into Nuke.

It intercepts a few DAP requests to establish a connection between the debugger and Nuke, and 
otherwise forwards all communications between the debugger and ptvsd normally.

## Installation

To install from repo,
- Open Sublime
- Install the "Debugger" plugin with Package Control if not done already
- In the "Preferences" menu, select "Browse Packages..."
- Clone this repository into the folder opened by Sublime

## Use

- Open the project you want to debug
    - If the debugger isn't open, select "Open" in the "Debugger" menu option
    - If it still doesn't open, ensure your project settings (Project -> Edit Project) are not empty, then try again
- Under the "Debugger" menu, select "Add or Select Configuration"
- Select "Add Configuration" from the suggestions
- There should be a "Nuke: Python 2 Debugging" option, click on it
- You should have your project settings automatically opened, edited with the configuration
- Save your project settings
- Go back to Debugger -> Add or Select Configuration, and select "Nuke: Python 2 Debugging"

The Nuke Adapter should now be functional just by pressing play.

If it is your first time installing the adapter and Nuke is already open, make sure to restart Nuke first (a first-time setup is performed).

## Note

Currently only tested on Windows
