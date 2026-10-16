from dotenv import load_dotenv
load_dotenv()
import os
import socket
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      
    pool_recycle=300,        
)


def _prefer_ipv4(dialect, conn_rec, cargs, cparams):
    """Connect over IPv4 when the host has an IPv4 address.

    On networks with broken IPv6 routing (common on home ISPs), libpq tries
    IPv6 first and hangs for tens of seconds or fails with "SSL SYSCALL error:
    EOF". `hostaddr` picks the address while `host` still drives TLS
    verification and SNI, which Neon uses to route the connection.
    """
    host = cparams.get("host")
    if not host or cparams.get("hostaddr") or host.startswith("/"):
        return
    try:
        cparams["hostaddr"] = socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
    except OSError:
        pass  # no IPv4 address: let libpq resolve as usual


if engine.dialect.name == "postgresql" and os.getenv("DB_PREFER_IPV4", "true").lower() in ("1", "true", "yes"):
    event.listen(engine, "do_connect", _prefer_ipv4)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()



def get_db():
    """FastAPI dependency: one DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
