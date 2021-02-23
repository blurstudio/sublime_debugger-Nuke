# A Debug Adapter for Debugging Python 2 within Autodesk 3ds Max

This adapter serves as a "middleman" between the Sublime Debugger plugin 
and a DAP implementation for python (ptvsd) injected into 3ds Max.

It intercepts a few DAP requests to establish a connection between the debugger and 3ds Max, and 
otherwise forwards all communications between the debugger and ptvsd normally.
