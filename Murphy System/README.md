# Murphy System - Minimal Working Implementation

## Overview
This directory contains a minimal Flask backend (`murphy_server.py`) and a static dashboard (`index.html`) for local demo purposes.

## Default Ports (Local)
✅ **Backend Server**: http://localhost:3002
✅ **Frontend Server**: http://localhost:8090
✅ **WebSocket**: ws://localhost:3002

## Access URLs
- **Frontend Dashboard**: http://localhost:8090
- **Backend API**: http://localhost:3002

## Features Implemented (Minimal Demo)

### Backend (murphy_server.py)
- ✅ REST API endpoints
- ✅ WebSocket real-time communication
- ✅ Agent management system
- ✅ State management system
- ✅ Artifact tracking
- ✅ Terminal command execution
- ✅ Error handling and logging
- ✅ CORS support

### Frontend (index.html)
- ✅ Interactive dashboard
- ✅ Real-time status updates
- ✅ Agent visualization
- ✅ State tracking
- ✅ Terminal interface
- ✅ System logging
- ✅ Responsive design

## How to Use

1. **Start the Backend**
   - `python3 murphy_server.py`

2. **Start the Frontend**
   - `python3 -m http.server 8090`

3. **Access the Dashboard**
   - Open the frontend URL in your browser
   - Wait for the system to connect (green status indicator)

4. **Initialize the System**
   - Click the "Initialize System" button
   - The system will create default agents and states

5. **Explore Features**
   - **Dashboard**: View system overview
   - **Agents**: See active agents and their roles
   - **States**: Track system states
   - **Terminal**: Execute commands
   - **System Log**: View real-time logs

## API Endpoints

### System Status
- `GET /api/status` - Get system status

### Initialization
- `POST /api/initialize` - Initialize the system

### Agents
- `GET /api/agents` - Get all agents
- `GET /api/agents/<id>` - Get specific agent
- `POST /api/agents` - Create new agent

### States
- `GET /api/states` - Get all states
- `GET /api/states/<id>` - Get specific state
- `POST /api/states` - Create new state

### Artifacts
- `GET /api/artifacts` - Get all artifacts
- `POST /api/artifacts` - Create new artifact

### WebSocket Events
- `connect` - Client connection
- `disconnect` - Client disconnection
- `ping/pong` - Heartbeat
- `terminal_command` - Execute terminal command
- `system_initialized` - System initialization event
- `agent_created` - Agent creation event
- `state_created` - State creation event

## Architecture

### Backend Structure
```
murphy_server.py
├── Flask App Setup
├── WebSocket Integration
├── API Endpoints
│   ├── System Status
│   ├── Agents
│   ├── States
│   └── Artifacts
├── WebSocket Events
├── Error Handlers
└── Main Server Loop
```

### Frontend Structure
```
index.html
├── HTML Structure
│   ├── Header
│   ├── Sidebar
│   ├── Content Area
│   └── Right Sidebar (Terminal)
├── CSS Styling
│   ├── Layout
│   ├── Components
│   └── Animations
└── JavaScript
    ├── API Calls
    ├── WebSocket Connection
    ├── UI Updates
    └── Event Handlers
```

## Default Agents
1. **Director** - Orchestration role
2. **Researcher** - Research role
3. **Analyst** - Analysis role

## Default States
1. **Initial State** - System initialized successfully

## Troubleshooting

### Connection Issues
- Check that both backend (port 3002) and frontend (port 8090) are running locally
- Verify the status indicator is green
- Check browser console for errors

### WebSocket Issues
- Ensure WebSocket connection is established
- Check that backend allows CORS connections
- Verify firewall settings

### API Errors
- Check server logs (`tail -f server.log`)
- Verify endpoints are correct
- Check system initialization status

## Server Logs

### Backend Log
```bash
tail -f server.log
```

### Frontend Log
```bash
tail -f frontend.log
```

## Development

### Starting the Backend
```bash
python3 murphy_server.py > server.log 2>&1 &
```

### Starting the Frontend
```bash
python3 -m http.server 8090 > frontend.log 2>&1 &
```

### Testing API Endpoints
```bash
# Check status
curl http://localhost:3002/api/status

# Initialize system
curl -X POST http://localhost:3002/api/initialize

# Get agents
curl http://localhost:3002/api/agents
```

## System Requirements

### Python Packages
- Flask
- Flask-SocketIO
- Flask-CORS

### Browser Requirements
- Modern web browser (Chrome, Firefox, Safari)
- JavaScript enabled
- WebSocket support

## Related Systems

- For the integrated runtime and full automation stack, see `Murphy System/murphy_integrated/README.md`.

## Future Enhancements

Potential improvements for the system:
- [ ] Add user authentication
- [ ] Implement database persistence
- [ ] Add more agent types
- [ ] Implement advanced visualizations
- [ ] Add file upload/download
- [ ] Implement agent collaboration
- [ ] Add more terminal commands
- [ ] Create API documentation
- [ ] Add performance monitoring
- [ ] Implement backup/restore

## Support

For issues or questions:
1. Check the system logs
2. Verify server status
3. Review API endpoints
4. Check WebSocket connection

## Version Information

- **Backend Version**: 1.0.0 (Minimal Working Version)
- **Frontend Version**: 1.0.0 (Clean Dashboard)
- **Last Updated**: 2026-01-29

## License

This is a development system for research and testing purposes.
