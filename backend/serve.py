"""One-process application launcher for native Windows and stateful hosting."""
import os
from pathlib import Path


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    import uvicorn
    host = os.environ.get('HOST', '0.0.0.0' if os.environ.get('RENDER') == 'true' else '127.0.0.1')
    port = int(os.environ.get('PORT', '8000'))
    if not 1 <= port <= 65535: raise SystemExit('PORT must be between 1 and 65535')
    uvicorn.run('backend.main:app', host=host, port=port, workers=1,
                loop='asyncio', http='h11', ws='none', proxy_headers=True,
                forwarded_allow_ips=os.environ.get('FORWARDED_ALLOW_IPS', '127.0.0.1'),
                access_log=False, timeout_keep_alive=5, timeout_graceful_shutdown=60,
                limit_concurrency=16)


if __name__ == '__main__': main()
