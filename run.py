#!/usr/bin/env python3
"""
Among Us IRL - Startup Script

Usage:
    python run.py              # Run server only (local development)
    python run.py --tunnel     # Run with Cloudflare tunnel (public access)
"""

import subprocess
import sys
import signal
import time
import argparse


def main():
    parser = argparse.ArgumentParser(description='Start Among Us IRL server')
    parser.add_argument('--tunnel', action='store_true', help='Start Cloudflare tunnel for public access')
    parser.add_argument('--port', type=int, default=8000, help='Port to run server on (default: 8000)')
    args = parser.parse_args()

    processes = []

    def cleanup(sig=None, frame=None):
        print('\nShutting down...')
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Start FastAPI server
    print(f'Starting server on port {args.port}...')
    server_process = subprocess.Popen([
        sys.executable, '-m', 'uvicorn',
        'server.main:app',
        '--host', '0.0.0.0',
        '--port', str(args.port),
        '--reload'
    ])
    processes.append(server_process)

    # Wait for server to start
    time.sleep(2)

    if args.tunnel:
        print('Starting Cloudflare tunnel...')
        print('(Install with: brew install cloudflared)')
        try:
            tunnel_process = subprocess.Popen([
                'cloudflared', 'tunnel', '--url', f'http://localhost:{args.port}'
            ])
            processes.append(tunnel_process)
            print('Tunnel starting... Look for the public URL above.')
        except FileNotFoundError:
            print('ERROR: cloudflared not found. Install with: brew install cloudflared')
            print('Continuing without tunnel...')
    else:
        print(f'\nServer running at: http://localhost:{args.port}')
        print('Add --tunnel flag to get a public URL for phones')

    print('\nPress Ctrl+C to stop\n')

    # Keep running
    try:
        server_process.wait()
    except KeyboardInterrupt:
        cleanup()


if __name__ == '__main__':
    main()
