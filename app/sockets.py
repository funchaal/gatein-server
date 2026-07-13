# app/sockets.py
# DEPRECATED: Socket.IO logic has been refactored and organized inside app/api/sockets/.
# This file is kept as a backward-compatibility bridge to prevent breaking imports in other modules.

from app.api.sockets.connection import sio, socket_app
from app.api.sockets.handlers.checkin import active_terminals