from db import Base, engine
from models import session, message

if __name__ == "__main__":
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done ✅")