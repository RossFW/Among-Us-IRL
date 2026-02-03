# Among Us IRL

A Progressive Web App for playing Among Us in real life. Players use their phones to see their roles, track tasks, and call meetings.

## Quick Start

### Start the Server
```bash
./start.sh
```
cd ~/Desktop/Among\ Us/among-us-pwa
./start.sh

This shows you the URLs:
- **Computer**: http://localhost:8000
- **Phone** (same WiFi): http://YOUR_LOCAL_IP:8000

### Game Day (External Access)
When friends need to connect from outside your WiFi:
```bash
# Terminal 1
./start.sh

# Terminal 2
cloudflared tunnel --url http://localhost:8000
```
Share the generated `*.trycloudflare.com` URL.

---

## Manual Commands

```bash
# Navigate to project
cd ~/Desktop/Among\ Us/among-us-pwa

# Activate virtual environment
source venv/bin/activate

# Kill old server (if running)
lsof -ti:8000 | xargs kill -9

# Start server
uvicorn server.main:app --host 0.0.0.0 --port 8000

# (Optional) In another terminal, start tunnel for external access
cloudflared tunnel --url http://localhost:8000
```

---

## Testing Tips

**Multi-player on one computer:**
- Open multiple incognito/private browser windows
- Each window = one player

**Phone testing:**
- Make sure phone is on same WiFi as computer
- Use the IP address shown by `./start.sh`

---

## How to Play

1. **Create a game** - One person creates the game and gets a 4-letter code
2. **Share the code** - Other players enter their name and the code to join
3. **Configure** - The host sets the number of tasks, impostors, and special roles
4. **Start** - When everyone's ready, the host starts the game
5. **Play** - Players see their role and tasks on their phone:
   - **Crewmates**: Go complete your physical tasks and tap to check them off
   - **Impostors**: Pretend to do tasks, eliminate crewmates
   - **Special roles**: Follow your unique win condition
6. **Meetings** - Anyone can call a meeting. Discuss and vote in person!
7. **Win** - Crewmates win by completing all tasks. Impostors win by eliminating enough crewmates.

## Roles & Win Conditions

| Role | Win Condition |
|------|---------------|
| **Crewmate** | Complete all tasks OR vote out all impostors |
| **Impostor** | Eliminate crewmates until impostors >= crewmates |
| **Sheriff** | Complete tasks AND shoot impostors (miss = you die!) |
| **Jester** | Get yourself voted out during a meeting |
| **Lone Wolf** | Be one of last 2 alive with no impostors remaining |
| **Minion** | Help impostors win (cannot kill, knows who impostors are) |

## Features

- **Multiple roles**: Crewmate, Impostor, Sheriff, Jester, Lone Wolf, Minion
- **Real-time updates**: Task progress syncs across all players
- **Reconnection**: If someone closes the app, they just reopen and rejoin
- **Mobile-first**: Designed for phones, installable as PWA
- **Meeting system**: Call meetings, see task progress, then vote in person
- **Custom tasks**: Add or remove physical tasks before the game
- **Kill cooldown timer**: Visual timer with vibration notification
- **Leave game**: Exit lobby if you joined wrong game

## Troubleshooting

**"Port 8000 already in use"**
```bash
lsof -ti:8000 | xargs kill -9
```

**Phone can't connect**
- Same WiFi as computer?
- Try the IP shown by `./start.sh`

---

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Vanilla JS, CSS
- **Real-time**: WebSockets
- **Hosting**: Self-hosted with Cloudflare Tunnel

## License

MIT
