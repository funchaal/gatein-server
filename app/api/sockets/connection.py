import socketio
from app.api.sockets.handlers.checkin import CheckinNamespace, active_terminals

# Create the asynchronous Socket.IO server instance
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# Create the standalone ASGI application wrapping python-socketio
socket_app = socketio.ASGIApp(sio)

# Register namespace class-based handlers
sio.register_namespace(CheckinNamespace('/checkin'))
