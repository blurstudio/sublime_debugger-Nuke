# A Debug Adapter for Debugging Python 2 within Foundry's Nuke

This adapter serves as a "middleman" between the Sublime Debugger plugin 
and a DAP implementation for python (ptvsd) injected into Nuke.

It intercepts a few DAP requests to establish a connection between the debugger and Nuke, and 
otherwise forwards all communications between the debugger and ptvsd normally.
