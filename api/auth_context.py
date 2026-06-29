from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    member_id: int
    user_id: int
    token: str

    @classmethod
    def from_login_data(cls, login_data: dict) -> AuthContext:
        return cls(
            member_id=int(login_data["memberId"]),
            user_id=int(login_data["userId"]),
            token=str(login_data["token"]),
        )
