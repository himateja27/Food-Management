from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from app.models import User
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest


class RegistrationConflict(Exception):
    pass


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.password_hasher = PasswordHash.recommended()

    def register(self, data: RegisterRequest) -> User:
        email = data.email.strip().lower()
        if self.users.get_by_email(email) is not None:
            raise RegistrationConflict("An account with this email already exists")
        user = User(
            email=email,
            full_name=data.full_name.strip(),
            password_hash=self.password_hasher.hash(data.password.get_secret_value()),
            role="USER",
            is_active=True,
        )
        try:
            self.users.add(user)
            self.session.commit()
            self.session.refresh(user)
            return user
        except IntegrityError as exc:
            self.session.rollback()
            raise RegistrationConflict("An account with this email already exists") from exc
        except Exception:
            self.session.rollback()
            raise
